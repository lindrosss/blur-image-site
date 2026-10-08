# Blur Image Online site

Static site for the Chrome extension: home, post-install welcome, help, and
privacy. Plain HTML and CSS — no build step. Same structure as JSON Checker’s
`welcome-site`.

```
index.html              Home — product pitch + Install
welcome/index.html      Post-install: pin (1–2), then open (3)
help/index.html         How to open, edit, and save
privacy/index.html      Privacy policy for the Web Store listing
assets/welcome.css
assets/img/             Icons + screenshot WebP (light/dark, 1x/2x)
tools/prepare_screens.py
```

| URL | Page |
| --- | --- |
| `/` | Home |
| `/welcome/` | Welcome (open after install) |
| `/help/` | Help / support URL |
| `/privacy/` | Privacy policy URL |

## Install button

Every page currently links Install to `#install`. Replace that with the Chrome
Web Store listing URL once the extension is published, for example:

```
https://chromewebstore.google.com/detail/…/YOUR-ID
```

## Screenshots

Full-window branded sources (3420×1700) are kept in `assets/img/source/`.
The welcome page uses a **top-right crop** so the puzzle piece, pin, and toolbar
icon stay readable.

```bash
python3 BlurImageOnline/welcome-site/tools/prepare_screens.py   # needs Pillow
```

Crops (full-window coordinates) and SVG `viewBox` sizes:

| Shot | Crop box | viewBox |
| --- | --- | --- |
| step-pin | `(2150, 0, 3420, 900)` | `0 0 1270 900` |
| step-open | `(2300, 0, 3420, 400)` | `0 0 1120 400` |

If you change the crop, update the marker coordinates in `welcome/index.html`.

## Opening welcome on install

```js
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    void chrome.tabs.create({ url: 'https://YOUR-DOMAIN/welcome/' })
  }
})
```

Use `/help/` as the Web Store support URL and `/privacy/` as the privacy policy
URL.
