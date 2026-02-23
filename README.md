# text-png-to-pdf

將 plain text/markdown 文字檔與 PNG 圖檔整合後輸出成 PDF。

## 功能

- 支援輸入 1+ 個文字檔 (`.txt`, `.md`, `.markdown`)
- 支援輸入 0+ 個 PNG 檔案
- 文字中可使用 `<image_name.png>` 佔位符，輸出 PDF 時會以該圖片換行取代
- 若所有文字檔都沒有 `<*.png>` 佔位符，則所有圖片會附加在 PDF 最後
- plain text 內容使用左對齊，不會強制置中
- markdown 內容會保留常見樣式（標題、段落、清單、粗體/斜體/程式碼/連結）

## 安裝

```bash
pip install -r requirements.txt
```

## 使用方式

```bash
python generate_pdf.py \
  --texts report.txt summary.md \
  --images hrv_chart_14d.png stress.png \
  --font /path/to/font.ttf \
  --output output.pdf
```

### 佔位符範例

文字內容：

```text
近14日的HRV趨勢如下：<hrv_chart_14d.png>
```

輸出 PDF 時，`<hrv_chart_14d.png>` 會被圖片取代，並獨立換行顯示。

## 參數

- `--texts`：必填，至少一個文字檔
- `--images`：選填，零個以上 PNG 圖檔
- `--font`：選填，指定 TTF/TTC/OTF 字型檔；建議固定指定以確保跨機器一致
- `--output`：必填，輸出 PDF 路徑

## 字型與相容性

- 程式會使用可內嵌（embedded subset）的字型輸出 PDF，避免目標機器缺字型時顯示異常。
- 若未指定 `--font`，程式會嘗試系統常見 CJK 字型路徑；若都不可用會直接報錯（不再退回非穩定 fallback）。
- 最穩定做法：在專案中放一份可授權字型並固定透過 `--font` 指定。
