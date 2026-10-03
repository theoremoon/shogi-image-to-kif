# 同梱素材と依存

## サンプル画像

各画像の作者・原ページ・ライセンスは `data/samples/manifest.json` を参照。CC0とCC BY-SA 4.0の画像を含む。再配布時はこのマニフェストも保持する。画像・派生素材には各画像のライセンスが適用され、アプリのコードのMITライセンスとは別。

## 駒テンプレート

`src/shogi_image_to_kif/assets/templates.npz` はCommonsの2枚の画像から抽出した駒と、フォントの描画画像から作った形状データ。出典・作者・ライセンス・原画像ハッシュは隣の `templates-sources.json`。CommonsのCC BY-SA 4.0の参照素材からの派生部分には [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) が適用される。アプリのMITライセンスをこの素材に適用しない。元のフォントファイルやアウトラインは配布しない。

## 日本語OCRモデル

`assets/jpn.traineddata` と `assets/jpn_vert.traineddata` は [tesseract-ocr/tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) の日本語/縦書き日本語モデル。Apache License 2.0。ライセンス本文は `assets/TESSDATA-LICENSE`、取得元とハッシュは `assets/ocr-sources.json`。

OCRエンジンTesseract本体は同梱しない。PATH上にインストールされている場合だけ使用する。見つからない場合は持ち駒・手番を手入力する。

## 検証用データ

ぴよ将棋の公開JavaScriptは配布しない。検証スクリプトは利用者が取得した元ファイルを読み込むか、ぴよ将棋WEB版の実ブラウザでKIF読み込みを検証する。検証結果と自分たちの出力KIFのみを `docs/` に保存する。

画面のスクリーンショットに公開サンプル画像が写る `docs/ui-desktop.png` / `docs/ui-mobile.png` には、[Hisha ochi.png](https://commons.wikimedia.org/wiki/File:Hisha_ochi.png) のCC BY-SA 4.0の素材が含まれる。作者の情報はマニフェストのcommons-008を参照。

## Python依存

NumPy・OpenCV・Pillowを実行依存として利用。python-shogiは独立パーサーによる検証専用の開発依存で、実行コードでは使用しない。各依存のライセンスは配布元に従う。依存バージョンは `uv.lock` に固定する。

将棋ウォーズの公式Q&Aに由来する画面画像・抽出字形はHEROZ等の権利者の素材。原画像は `data/local-samples/` のローカル検証用に保存し、Gitや公開サイトには含めない。抽出した数値字形参照は `assets/wars-templates.npz` として公開版に含める。画像と字形の出典はローカルmanifestと `assets/wars-template-sources.json` に保存する。アプリのMITライセンスをこれらの素材に適用しない。


## Webランタイム

GitHub Pages版はPyodide 0.28.1をjsDelivrから読み込む。PyodideはMPL 2.0、NumPyはBSD、OpenCV 4.xはApache 2.0、PillowはHPND系のライセンス。ランタイム・各パッケージのライセンスは [Pyodideの配布ファイル](https://cdn.jsdelivr.net/pyodide/v0.28.1/full/) と各公式配布元を参照する。アプリのコードとサードパーティ素材を区別する。公開版には日本語OCRモデルを含めない。
