# Development Notes

This repository contains the `evox_erp` Frappe app. Keep custom business logic here and do not modify Frappe or ERPNext core.

## Local Development

Use a Frappe development bench or the Frappe Docker devcontainer:

```bash
bench get-app https://github.com/adnanrayyan/evox_erp.git
bench --site evox-dev.localhost install-app evox_erp
bench --site evox-dev.localhost migrate
```

## Production-Like Local Stack

The local production helper scripts live in the sibling `evox-erp-infra` repository.

After pulling app changes into a bench:

```bash
bench --site SITE_NAME migrate
bench build --app evox_erp
bench --site SITE_NAME clear-cache
```

