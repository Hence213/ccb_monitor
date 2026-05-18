# 批量抓取产品历史净值
.venv/bin/python boc/fetch_boc_nav.py --update-db --products-csv boc/database/boc_products.csv --db-path boc/database/boc_product_detail.db --workers 8 --timeout 20
# 批量抓取产品最新额度
.venv/bin/python boc/fetch_boc_product_indiAmtRem.py --products-csv boc/database/boc_products.csv --db-path boc/database/boc_product_detail.db --workers 32 --timeout 20
