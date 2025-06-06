from notion_client import Client
from dotenv import load_dotenv
import os
import datetime
from yt_dlp import YoutubeDL
import requests
import json
from dataclasses import dataclass
import logging

# ======== Config Begin ========================================================
# .envを読み込む
load_dotenv()
# 環境変数として取得
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_VERSION = "2022-06-28"

# ログ設定
today = datetime.datetime.now().strftime("%Y%m%d")
# TODO: ログの保存先を.envで定義
log_path = os.path.expanduser(f"~/Downloads/sample-notion-get-db-log-{today}.txt")
logging.basicConfig(
    filename=log_path,
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# ======== Config End ==========================================================
notion = Client(auth=NOTION_TOKEN)

@dataclass
class VideoInfo:
    """
    動画の情報を格納するためのデータクラス。

    属性:
        video_title (str): 動画のタイトル。
        video_filepath (str): 動画ファイルのパス。
        thumbnail_filepath (str): サムネイル画像のファイルパス。
    """
    video_title: str
    video_filepath: str
    thumbnail_filepath: str

@dataclass
class MimeTypeInfo:
    """
    MIMEタイプと対応するファイルタイプの情報を表すデータクラス。

    属性:
        mime_type (str): MIMEタイプの文字列（例: 'image/png'）。
        file_type (str): 対応するファイルタイプで、Notionのアップロード時に使用（例: 'image, video'）。
    """
    mime_type: str
    file_type: str

# ログ出力関数
def log(message: str, level: str = "info") -> None:
    print(message)
    if level == "info":
        logging.info(message)
    elif level == "error":
        logging.error(message)
    elif level == "warning":
        logging.warning(message)
    else:
        logging.debug(message)

# Notionデータベースからアイテムを取得する関数
def get_items(database_id) -> list:
    try:
        response = notion.databases.query(
            database_id=database_id,
            # プロパティ「処理済」が未チェックのアイテムを取得
            filter={
                "property": "処理済",
                "checkbox": {
                    "equals": False
                }
            }
        )
        return response.get("results", [])
    
    # 何かしらのエラーが発生した場合は空のリストを返す
    except Exception as e:
        log(f"Error retrieving items: {e}", level="error")
        return []

# アイテムのプロパティからURLを取得する関数
def get_item_propertie_url(item) -> str:
    # アイテムのプロパティからURLを取得
    try:
        if 'URL' in item['properties']:
            return item['properties']['URL']['url']
        else:
            return None
    except Exception as e:
        log(f"Error retrieving URL from item: {e}", level="error")
        return None

# 動画ファイル、サムネイルファイルをダウンロードして情報を返す関数
def download_file(url: str, output_dir: str = "~/Downloads") -> VideoInfo:
    outtmpl = f"{output_dir}/%(title)s_%(id)s.%(ext)s"

    ydl_opts = {
        "outtmpl": outtmpl,
        "writethumbnail": True,  # typo fixed from "writethiumbnail"
        "format": "bv[ext=mp4]+ba[ext=m4a]/bv+ba/best[ext=mp4]/best",
        "age_limit": 1985
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get("title")
            video_filepath = ydl.prepare_filename(info)

            # サムネイルファイルパスを探す
            thumbnail_filepath = None
            for thumb in info.get("thumbnails", []):
                if "filepath" in thumb:
                    thumbnail_filepath = thumb["filepath"]
                    break

            log(f"✅ ダウンロード成功: {video_filepath}")
            return VideoInfo(
                video_title=video_title,
                video_filepath=video_filepath,
                thumbnail_filepath=thumbnail_filepath
            )

    except Exception as e:
        log(f"Error downloading file from URL {url}: {e}", level="error")
        return None

# 指定したNotionページ内のすべての子ブロック（コンテンツ）を削除する関数
def delete_page_content(page_id: str) -> bool:
    """
    指定したNotionページ内のすべての子ブロック（コンテンツ）を削除します。
    引数:
        page_id (str): コンテンツを削除するNotionページのID。
    戻り値:
        bool: すべての子ブロックの削除に成功した場合はTrue、失敗した場合はFalse。
    例外:
        削除処理中に例外が発生した場合はエラーメッセージを出力します。
    """

    try:
        # 1. ページ内の子ブロックを取得
        children = notion.blocks.children.list(block_id=page_id)["results"]

        # 2. 各ブロックを削除
        for block in children:
            block_id = block["id"]
            notion.blocks.delete(block_id)
        
        return True

    except Exception as e:
        log(f"Error deleting content from page {page_id}: {e}", level="error")
        return False

# 指定したNotionページのタイトルを変更する関数
def change_page_title(page_id: str, new_title: str) -> bool:
    """
    指定したNotionページのタイトルを変更します。
    引数:
        page_id (str): タイトルを変更するNotionページのID。
        new_title (str): 新しいタイトル。
    戻り値:
        bool: タイトルの変更に成功した場合はTrue、失敗した場合はFalse。
    例外:
        タイトル変更中に例外が発生した場合はエラーメッセージを出力します。
    """

    try:
        # ページのプロパティを更新
        notion.pages.update(
            page_id=page_id,
            properties={
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": new_title
                            }
                        }
                    ]
                }
            }
        )
        return True

    except Exception as e:
        log(f"Error changing title for page {page_id}: {e}", level="error")
        return False

# 指定したNotionページの末尾にファイルをアップロードする関数
def upload_file_to_notion(page_id: str, filepath: str) -> None:
    # TODO: 20MBを超えるファイルのアップロード
    try:
        # 20MB 以下なら single_part、20MB 超なら multi_part とする（Notion APIの仕様）
        file_size = os.path.getsize(filepath)
        file_name = os.path.basename(filepath)
        mode = "single_part" if file_size <= 20 * 1024 * 1024 else "multi_part"

        mime_type_info = get_mime_type_from_extension(filepath)

        # Step 1: Create a File Upload object
        payload ={
            "filename": file_name,
        }

        file_create_response = requests.post("https://api.notion.com/v1/file_uploads",
                                             json=payload,
                                             headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "accept": "application/json",
            "content-type": "application/json",
            "Notion-Version": NOTION_VERSION
        })

        if file_create_response.status_code != 200:
            raise Exception(
                f"File creation failed with status code {file_create_response.status_code}: {file_create_response.text}"
            )
        
        file_upload_id = json.loads(file_create_response.text)['id']

        # Step 2: Upload file contents
        with open(filepath, "rb") as f:
            # Provide the MIME content type of the file as the 3rd argument.
            files = {
                "file": (file_name, f, mime_type_info.mime_type)
            }

            response = requests.post(
                f"https://api.notion.com/v1/file_uploads/{file_upload_id}/send",
                headers={
                    "Authorization": f"Bearer {NOTION_TOKEN}",
                    "Notion-Version": NOTION_VERSION
                },
                files=files
            )

            if response.status_code != 200:
                raise Exception(
                    f"File upload failed with status code {response.status_code}: {response.text}")
            
        # Step 3: Attach the file to a page or block

        url = f"https://api.notion.com/v1/blocks/{page_id}/children"

        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION
        }

        # MIMEタイプによってdataが変わる
        data = {
            "children": [
                {
                    "type": mime_type_info.file_type,
                    mime_type_info.file_type: {
                        "caption": [
                            {
                                "type": "text",
                                "text": {
                                    "content": file_name,
                                    "link": None
                                },
                                "annotations": {
                                    "bold": False,
                                    "italic": False,
                                    "strikethrough": False,
                                    "underline": False,
                                    "code": False,
                                    "color": "default"
                                },
                                "plain_text": file_name,
                                "href": "null"
                            }
                        ],
                        "type": "file_upload",
                        "file_upload": {
                            "id": file_upload_id
                        }
                    }
                }
            ]
        }

        # ページの末尾にファイルを添付する
        response = requests.patch(url, headers=headers, data=json.dumps(data))

        if response.status_code != 200:
            raise Exception(
                f"Failed to attach file to page with status code {response.status_code}: {response.text}"
            )

        log(f"✅ Notionにアップロード完了: {file_name}")

    except Exception as e:
        log(f"❌ Notionへのアップロード失敗: {e}", level="error")

# ファイルパスの拡張子が.imageの場合、.jpgに名称変更する関数
def rename_image2jpg_extension(filepath: str) -> str:
    """
    指定されたファイルパスの拡張子が.imageの場合、.jpgに変更します。
    Args:
        filepath (str): 変更対象のファイルパス。
    Returns:
        str: 拡張子を変更した新しいファイルパス。
    """
    if filepath.endswith(".image"):
        new_filepath = filepath[:-6] + ".jpg"
        os.rename(filepath, new_filepath)
        log(f"✅ 拡張子が「.image」だったのでファイル名を変更しました: {filepath} -> {new_filepath}")
        return new_filepath
    return filepath

# ファイルパスを渡して拡張子からMIMEタイプを返す関数
def get_mime_type_from_extension(filepath: str) -> MimeTypeInfo:
    extension = os.path.splitext(filepath)[1].lower()
    mime_types = {
        ".mp4": MimeTypeInfo(mime_type="application/mp4", file_type="video"),
        ".jpg": MimeTypeInfo(mime_type="image/jpeg", file_type="image"),
        ".jpeg": MimeTypeInfo(mime_type="image/jpeg", file_type="image"),
        ".png": MimeTypeInfo(mime_type="image/png", file_type="image"),
        ".gif": MimeTypeInfo(mime_type="image/gif", file_type="image"),
    }
    return mime_types.get(extension, MimeTypeInfo(mime_type="application/octet-stream", file_type="image"))

# Notionのページのプロパティ「処理済」を操作する関数
def change_item_processed_status(
        item_id: str, property_name: str = "処理済", status: bool = True) -> bool:
    """
    アイテムのプロパティ「処理済」を更新する関数。

    Args:
        item_id (str): 更新するアイテムのID。
        status (bool): 新しいステータス（True: 処理済, False: 未処理）。
    """
    try:
        notion.pages.update(
            page_id=item_id,
            properties={
                property_name: {
                    "checkbox": status
                }
            }
        )
        log(f"✅ アイテム {item_id} の「{property_name}」ステータスを更新しました。")
        return True
    
    except Exception as e:
        log(f"❌ アイテム {item_id} の「{property_name}」ステータス更新に失敗: {e}", level="error")
        return False

# ======== Entry Point =========================================================
def main() -> None:
    # データベースからアイテムを取得
    items = get_items(NOTION_DATABASE_ID)

    if not items:
        log("⚠️Notionデータベースに対象のアイテムがありません。", level="warning")
        return

    for item in items:
        # TODO: tryで囲って、logはすべてここで行うようにする
        # アイテムのプロパティからURLを取得
        log(f"▶ アイテムID「{item['id']}」の処理を開始します。")
        url = get_item_propertie_url(item)

        if url is None:
            log(f"❌ アイテム {item['id']} に「URL」プロパティがありません。", level="error")
            return
        log(f"▶ アイテムID「{item['id']}」のURL: {url}")

        # URLからファイルをダウンロード
        log(f"▶ URL「{url}」の動画をダウンロード中...")
        video_info: VideoInfo = download_file(url)

        log(f"ダウンロードした動画のタイトル: {video_info.video_title}")
        log(f"ダウンロードした動画のファイルパス: {video_info.video_filepath}")
        log(f"ダウンロードしたサムネイルのファイルパス: {video_info.thumbnail_filepath}")

        if not video_info.video_filepath:
            log(f"❌ URL「{url}」のダウンロードに失敗しました。", level="error")
            continue
        log(f"✅ URL「{url}」のダウンロードが完了しました。")

        # ダウンロードが完了したらNotionのページ内のコンテンツを削除
        # TODO: Xからのダウンロードはコンテンツを削除しないようにする
        log(f"▶ アイテムID「{item['id']}」のページコンテンツを削除中...")
        if not delete_page_content(item["id"]):
            log(f"❌ ページのコンテンツ削除失敗: {item['id']}", level="error")
            # コンテンツの削除に失敗しても取り急ぎ次に進む

        # ダウンロードが完了したらNotionのページタイトルを動画のタイトルに変更
        log(f"▶ アイテムID「{item['id']}」のページタイトルを変更中...")
        if not change_page_title(item["id"], video_info.video_title):
            log(f"❌ ページタイトルの変更失敗: {item['id']}", level="error")
            # タイトルの変更に失敗しても取り急ぎ次に進む

        # ファイルがダウンロードできたら、Notionに動画をアップロード
        log(f"▶ アイテムID「{item['id']}」の動画をNotionにアップロード中...")
        upload_file_to_notion(item["id"], video_info.video_filepath)

        # サムネイルの拡張子が.imageなら.jpgに変更
        log(f"▶ アイテムID「{item['id']}」のサムネイルの拡張子を確認中...")
        video_info.thumbnail_filepath = rename_image2jpg_extension(video_info.thumbnail_filepath)

        # 動画のアップロードの次に画像を添付する
        log(f"▶ アイテムID「{item['id']}」のサムネイルをNotionにアップロード中...")
        upload_file_to_notion(item["id"], video_info.thumbnail_filepath)

        # アイテムのプロパティ「処理済」をチェックにする
        log(f"▶ アイテムID「{item['id']}」の「処理済」ステータスを更新中...")
        if not change_item_processed_status(item["id"]):
            log(f"❌ アイテム {item['id']} の「処理済」ステータス更新に失敗", level="error")
            # ステータスの更新に失敗しても取り急ぎ次に進む
        
        log(f"✅ アイテム {item['id']} の処理が完了しました。")
        # Continue

    log("すべてのアイテムの処理が完了しました。")
# End

# ======== Main End ============================================================

main()
log("===== スクリプトが終了しました。\n\n")
exit(0)