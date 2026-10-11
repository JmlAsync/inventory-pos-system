# Outside files kept inside the project (v0.19.4)

These files used to load from the internet (jsDelivr and Google Fonts). They are stored here so every page
looks and works the same **without internet** (AGENTS.md rule D2). Do not edit them; to update one, replace it
with the same file from the named package version and change the version in this table and in AGENTS.md.

| Folder | Package and version | Licence | Files |
|---|---|---|---|
| `bootstrap/` | bootstrap 5.3.3 (npm) | MIT (`LICENSE.txt`) | `dist/css/bootstrap.min.css`, `dist/js/bootstrap.bundle.min.js` |
| `bootstrap-icons/` | bootstrap-icons 1.11.3 (npm) | MIT (`LICENSE.txt`) | `font/bootstrap-icons.min.css`, `font/fonts/bootstrap-icons.woff2` and `.woff` |
| `inter/` | @fontsource/inter 5.2.8 (npm) | SIL Open Font License 1.1 (`LICENSE.txt`) | `files/inter-latin(-ext)-400/500/600/700-normal.woff2`; `inter.css` written for this project |

The Bootstrap files end with a `sourceMappingURL` comment; the `.map` files are left out on purpose (they are only
used by a browser's developer tools, which then show a harmless "not found").
