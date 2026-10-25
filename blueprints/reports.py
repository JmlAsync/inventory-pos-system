"""Home with today's numbers, and the Sales Report (v0.10.0, v0.13.0). Moved from app.py in v0.25.0 (DEC-027).
These pages only read. v0.31.0: the money is net of voids and refunds."""
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models import db, Product, Ingredient, Sale, SaleAdjustment, to_money
from common import LOW_STOCK_THRESHOLD, PAYMENT_METHODS, admin_required, shop_now, shop_day_start_utc
from store.stock import stock_levels
from store import adjustments as adjustment_store   # v0.31.0

bp = Blueprint('reports', __name__)


def money_in_period(sales, period_start, period_end):
    """Gross, voids, refunds and net for a period, and the net money by payment method (v0.31.0, DEC-033, plan §4.1).
    A void cancels its sale on the sale's own day (a void is only allowed that day). A refund is new money going out
    on the day it was given, even for an older receipt. By method: what came in that way, minus what went back that
    way, so "Cash" is what should be in the drawer."""
    refunds = (SaleAdjustment.query.filter(SaleAdjustment.kind == 'refund', SaleAdjustment.status == 'approved',
                                           SaleAdjustment.decided_at >= period_start,
                                           SaleAdjustment.decided_at < period_end).all())
    voids = [a for sale in sales for a in sale.adjustments if a.kind == 'void' and a.status == 'approved']
    gross = to_money(sum(sale.total for sale in sales))
    voided = to_money(sum(a.total for a in voids))
    refunded = to_money(sum(a.total for a in refunds))
    by_method = {key: to_money(sum(s.total for s in sales if s.payment_method == key)
                               - sum(a.total for a in voids + refunds if a.method == key))
                 for key in PAYMENT_METHODS}
    return {'gross': gross, 'voids': voided, 'void_count': len(voids), 'refunds': refunded,
            'refund_count': len(refunds), 'net': gross - voided - refunded, 'by_method': by_method}


@bp.route('/')
def home():
    """Home page. Logged-in users see today's numbers and shortcuts (v0.13.0)."""
    stats = None
    if current_user.is_authenticated:
        start_of_today = shop_day_start_utc(shop_now().date())   # v0.23.1: the shop's day, in UTC
        todays_sales = Sale.query.filter(Sale.created_at >= start_of_today).all()
        # v0.31.0: voided sales don't count, and today's refunds are taken off
        money = money_in_period(todays_sales, start_of_today, shop_day_start_utc(shop_now().date() + timedelta(days=1)))
        stats = {
            'products': Product.query.count(),
            'low_stock': sum(1 for n in stock_levels(Product.query.all()).values() if n <= LOW_STOCK_THRESHOLD),
            'low_ingredients': Ingredient.query.filter(Ingredient.quantity <= Ingredient.low_at).count(),
            'sales_today': sum(1 for sale in todays_sales if not sale.voided_at),
            'revenue_today': money['net'],
        }
    return render_template('home.html', stats=stats, today=shop_now().date())


# ---------------- Sales report (v0.10.0) ----------------

# Dates the report accepts (v0.10.0)
EARLIEST_DATE = date(2000, 1, 1)
LATEST_DATE = date(2100, 12, 31)


@bp.route('/reports/sales')
@login_required
@admin_required
def sales_report():
    """Totals, list of sales and top products for a date range (default: today)."""
    today = shop_now().date()   # v0.23.1: today in the shop
    error = None
    # Dates arrive in the address as text, e.g. /reports/sales?start=2026-10-08&end=2026-10-08
    try:
        start = datetime.strptime(request.args.get('start', today.isoformat()), '%Y-%m-%d').date()
        end = datetime.strptime(request.args.get('end', today.isoformat()), '%Y-%m-%d').date()
        # Realistic range only: a date like 9999-12-31 has no "next day" and would crash below
        if not (EARLIEST_DATE <= start <= LATEST_DATE and EARLIEST_DATE <= end <= LATEST_DATE):
            raise ValueError
    except ValueError:
        start = end = today
        error = 'Please choose real dates between 2000 and 2100, so showing today instead.'
    if start > end:
        start, end = end, start   # swap them if entered the wrong way round

    # From the start of the first day up to (but not including) the day after the last day, on the
    # shop's clock, turned into UTC because that is how sales are stored (v0.23.1)
    period_start = shop_day_start_utc(start)
    period_end = shop_day_start_utc(end + timedelta(days=1))
    in_period = (Sale.created_at >= period_start) & (Sale.created_at < period_end)

    sales = Sale.query.filter(in_period).order_by(Sale.created_at.desc()).all()
    money = money_in_period(sales, period_start, period_end)   # v0.31.0: gross, voids, refunds, net

    # Top 5 products by units sold (v0.10.1). Grouped by PRODUCT (its id), not by name,
    # so a product renamed after being sold still counts as one product.
    # The name shown is the one used in its most recent sale.
    # v0.31.0: units are what the customers kept: voided sales and refunded items don't count.
    totals = {}   # product id -> {'name', 'units', 'revenue', 'last_sold'}
    items_sold = 0
    for sale in sales:
        if sale.voided_at:
            continue
        for item in sale.items:
            kept = item.quantity - (item.refunded_quantity or 0)
            if kept <= 0:
                continue
            items_sold += kept
            row = totals.setdefault(item.product_id, {'name': item.product_name, 'units': 0,
                                                      'revenue': 0, 'last_sold': sale.created_at})
            row['units'] += kept
            row['revenue'] += item.unit_price * kept
            if sale.created_at >= row['last_sold']:   # keep the most recent name
                row['name'], row['last_sold'] = item.product_name, sale.created_at
    best = sorted(totals.values(), key=lambda row: row['units'], reverse=True)[:5]
    top_products = [(row['name'], row['units'], round(row['revenue'], 2)) for row in best]

    # Money by payment method (v0.15.0): what should be in the drawer vs. in GCash; since v0.31.0 after voids and
    # refunds given back that way
    # v0.31.0 (owner's decision 2026-10-25): the void requests waiting for an admin, and the period's voids and
    # refunds, are on this page too, so all the money is in one place
    return render_template('sales_report.html', sales=sales, revenue=money['net'], money=money,
                           items_sold=items_sold, top_products=top_products,
                           by_method=money['by_method'], start=start, end=end, error=error,
                           waiting=adjustment_store.waiting_voids(), sold_today=adjustment_store.sold_today,
                           adjustments=adjustment_store.decided_between(period_start, period_end))
