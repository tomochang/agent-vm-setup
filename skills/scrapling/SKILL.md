---
name: scrapling
description: Scraplingでウェブサイトをスクレイピングする。web_fetchで取れないJS重いサイトやCloudflare保護サイトに使う。
---

# /scrapling - Web Scraping with Scrapling

## いつ使うか

- `web_fetch`で取れない時（JS必須、Cloudflare、bot検出）
- ユーザーが`/scrapling`で明示的に指示した時
- CSSセレクタ/XPathで精密にデータ抽出したい時
- サイトの構造変更に追従したい時（適応型パーサー）

## コマンド

```
/scrapling <URL>                    # 自動判定でフェッチ、主要コンテンツ抽出
/scrapling <URL> <CSSセレクタ>       # 特定要素を抽出
/scrapling <URL> --stealth          # StealthyFetcher強制（bot対策回避）
/scrapling <URL> --dynamic          # DynamicFetcher強制（JS実行）
```

## 実行方法

### venv有効化（必須）

```bash
source /home/openclaw/.openclaw/workspace/tools/scrapling-env/bin/activate
```

### Fetcher選択基準

| 条件 | Fetcher | 速度 |
|------|---------|------|
| 静的HTML、API | `Fetcher` | 最速（<1s） |
| JS必須（SPA等） | `DynamicFetcher` | 中（3-5s） |
| Cloudflare/bot対策 | `StealthyFetcher` | 遅め（4-8s） |

**デフォルト: まずFetcherで試す → 失敗 or 内容が空ならStealthyFetcherにフォールバック**

### 基本パターン

```python
from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher

# 静的サイト
page = Fetcher.get('https://example.com')

# JS必須サイト
page = DynamicFetcher.fetch('https://example.com', headless=True, network_idle=True)

# bot対策サイト
page = StealthyFetcher.fetch('https://example.com', headless=True, network_idle=True)
```

### データ抽出

```python
# CSSセレクタ
titles = page.css('h1::text').getall()
links = page.css('a::attr(href)').getall()

# XPath
items = page.xpath('//div[@class="item"]/text()').getall()

# テキスト検索
elements = page.find_by_text('キーワード')

# 類似要素検索（1つ見つければ類似を自動検出）
first = page.css('.product')[0]
all_similar = first.find_similar()
```

### 適応型パーサー（サイト変更追従）

```python
# 初回: auto_save=Trueで保存
Fetcher.adaptive = True
page = Fetcher.get('https://example.com')
items = page.css('.old-class', auto_save=True)

# サイトリニューアル後: adaptive=Trueで再特定
items = page.css('.old-class', adaptive=True)
```

## 注意事項

- **利用規約を確認してからスクレイピングする**
- VPSのヘッドレス環境で動作確認済み
- StealthyFetcher/DynamicFetcherはChromium起動するためメモリ消費大（同時実行は避ける）
- `Fetcher.get()` と `StealthyFetcher.fetch()` でメソッド名が違うので注意

## venv管理

- **場所:** `tools/scrapling-env/`
- **gitignore済み**（117MB超のためGitHub push不可）
- **再作成:** `python3 -m venv tools/scrapling-env && source tools/scrapling-env/bin/activate && pip install "scrapling[all]" && scrapling install`
