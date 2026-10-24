"""Home with today's numbers, and the Sales Report (v0.10.0, v0.13.0). Moved from app.py in v0.25.0 (DEC-027),
unchanged: these pages only read."""
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, Product, Ingredient, Sale, SaleItem
from common import LOW_STOCK_THRESHOLD, PAYMENT_METHODS, admin_required, shop_now, shop_day_start_utc
from store.stock import stock_levels

bp = Blueprint('reports', __name__)


@bp.route('/')
def home():
    """Home page. Logged-in users see today's numbers and shortcuts (v0.13.0)."""
    stats = None
    if current_user.is_authenticated:
        start_of_today = shop_day_start_utc(shop_now().date())   # v0.23.1: the shop's day, in UTC
        todays_sales = Sale.query.filter(Sale.created_at >= start_of_today).all()
        stats = {
            'products': Product.query.count(),
            'low_stock': sum(1 for n in stock_levels(Product.query.all()).values() if n <= LOW_STOCK_THRESHOLD),
            'low_ingredients': Ingredient.query.filter(Ingredient.quantity <= Ingredient.low_at).count(),
            'sales_today': len(todays_sales),
            'revenue_today': round(sum(sale.total for sale in todays_sales), 2),
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
    revenue = round(sum(sale.total for sale in sales), 2)

    # Top 5 products by units sold (v0.10.1). Grouped by PRODUCT (its id), not by name,
    # so a product renamed after being sold still counts as one product.
    # The name shown is the one used in its most recent sale.
    totals = {}   # product id -> {'name', 'units', 'revenue', 'last_sold'}
    for sale in sales:
        for item in sale.items:
            row = totals.setdefault(item.product_id, {'name': item.product_name, 'units': 0,
                                                      'revenue': 0, 'last_sold': sale.created_at})
            row['units'] += item.quantity
            row['revenue'] += item.subtotal
            if sale.created_at >= row['last_sold']:   # keep the most recent name
                row['name'], row['last_sold'] = item.product_name, sale.created_at
    best = sorted(totals.values(), key=lambda row: row['units'], reverse=True)[:5]
    top_products = [(row['name'], row['units'], round(row['revenue'], 2)) for row in best]
    # Total units sold in the period (coalesce turns "nothing" into 0 when there are no sales)
    items_sold = (db.session.query(func.coalesce(func.sum(SaleItem.quantity), 0))
                  .join(Sale).filter(in_period).scalar())

    # Money in by payment method (v0.15.0): what should be in the drawer vs. in GCash
    by_method = {key: round(sum(s.total for s in sales if s.payment_method == key), 2)
                 for key in PAYMENT_METHODS}

    return render_template('sales_report.html', sales=sales, revenue=revenue,
                           items_sold=items_sold, top_products=top_products,
                           by_method=by_method, start=start, end=end, error=error)
