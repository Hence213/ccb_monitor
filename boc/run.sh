# 批量抓取产品历史净值
.venv/bin/python boc/fetch_boc_nav.py --update-db --products-csv boc/data/boc_products.csv --db-path boc/data/boc_product_detail.db --workers 8 --timeout 20
# 批量抓取产品最新额度
.venv/bin/python boc/fetch_boc_product_indiAmtRem.py --products-csv boc/data/boc_products.csv --db-path boc/data/boc_product_detail.db --workers 8 --timeout 20