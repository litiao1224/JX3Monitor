# -*- coding: utf-8 -*-
"""Cloud exporter and uploader for JX3 Monitor.

Extracts data and uploads it to Tencent Cloud COS or Alibaba Cloud OSS.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import jx3_click_monitor as core
from src.config import INCOME_MEMORY_PATH

logger = logging.getLogger("jx3_monitor.cloud_exporter")


def extract_data(app: Any) -> Dict[str, Any]:
    """Extract statistics and growth records from the App instance."""
    # 1. Extract income records
    income_data = []
    total_income = 0.0
    total_expense = 0.0
    total_net = 0.0

    try:
        if INCOME_MEMORY_PATH.exists():
            raw_data = json.loads(INCOME_MEMORY_PATH.read_text(encoding="utf-8-sig"))
            records = raw_data.get("records", [])
            # Sort by recorded_at desc
            records.sort(key=lambda x: x.get("recorded_at", ""), reverse=True)
            
            # Calculate stats
            for r in records:
                try:
                    inc = float(r.get("income") or 0)
                    exp = float(r.get("expense") or 0)
                    total_income += inc
                    total_expense += exp
                    total_net += (inc - exp)
                except Exception:
                    pass
            
            # Keep last 50 records for display
            income_data = records[:50]
    except Exception as e:
        logger.error("Failed to extract income data: %s", repr(e))

    # 2. Extract growth records
    growth_data = []
    try:
        raw_growth = getattr(app, "growth_records", []) or []
        for rec in raw_growth:
            # Check if this record is filtered out by selection settings
            ownerkey = f"{rec.get('account', '')}:{rec.get('server', '')}:{rec.get('name', '')}"
            if ownerkey in getattr(app, "hidden_growth_ownerkeys", set()):
                continue
            if getattr(app, "growth_role_selection_initialized", False) and getattr(app, "selected_growth_ownerkeys", set()):
                if ownerkey not in app.selected_growth_ownerkeys:
                    continue

            # Keep only safe fields for web view
            growth_data.append({
                "account": rec.get("account") or "",
                "server": rec.get("server") or "",
                "name": rec.get("name") or "",
                "score": rec.get("score") or "",
                "dungeons": rec.get("dungeons") or [],
            })
    except Exception as e:
        logger.error("Failed to extract growth data: %s", repr(e))

    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "total_income": total_income,
            "total_expense": total_expense,
            "total_net": total_net,
            "role_count": len(growth_data)
        },
        "income_records": income_data,
        "growth_records": growth_data
    }


def generate_js_data(data: Dict[str, Any]) -> str:
    """Generate the data.js file content wrapping JSON in a global window variable."""
    serialized = json.dumps(data, ensure_ascii=False, indent=2)
    return f"window.JX3_MONITOR_DATA = {serialized};\n"


def upload_to_cos(
    local_path: Path,
    cloud_path: str,
    secret_id: str,
    secret_key: str,
    bucket: str,
    region: str
) -> None:
    """Upload file to Tencent Cloud COS."""
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        raise ImportError("未安装腾讯云 COS SDK，请运行: pip install cos-python-sdk-v5")

    config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=None)
    client = CosS3Client(config)

    with open(local_path, "rb") as fp:
        client.put_object(
            Bucket=bucket,
            Body=fp,
            Key=cloud_path,
            StorageClass="STANDARD",
            ContentType="application/javascript" if local_path.suffix == ".js" else "text/html"
        )
    logger.info("Successfully uploaded %s to COS:%s/%s", local_path.name, bucket, cloud_path)


def upload_to_oss(
    local_path: Path,
    cloud_path: str,
    access_key_id: str,
    access_key_secret: str,
    bucket_name: str,
    endpoint: str
) -> None:
    """Upload file to Alibaba Cloud OSS."""
    try:
        import oss2
    except ImportError:
        raise ImportError("未安装阿里云 OSS SDK，请运行: pip install oss2")

    auth = oss2.Auth(access_key_id, access_key_secret)
    # Automatically prepend http/https if missing
    if not endpoint.startswith(("http://", "https://")):
        endpoint = "https://" + endpoint
        
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    headers = {"Content-Type": "application/javascript" if local_path.suffix == ".js" else "text/html"}

    with open(local_path, "rb") as fp:
        bucket.put_object(cloud_path, fp, headers=headers)
    logger.info("Successfully uploaded %s to OSS:%s/%s", local_path.name, bucket_name, cloud_path)


def export_and_upload(app: Any, upload_html: bool = False) -> str:
    """Extract, generate data.js, and upload to the configured cloud provider.

    Returns the target Web page URL if successful.
    """
    cfg = app.config_data
    if not cfg.get("cloud_sync_enabled"):
        raise ValueError("未启用云同步功能")

    provider = cfg.get("cloud_provider", "cos")
    secret_id = cfg.get("cloud_secret_id", "").strip()
    secret_key = cfg.get("cloud_secret_key", "").strip()
    bucket = cfg.get("cloud_bucket", "").strip()
    
    if not secret_id or not secret_key or not bucket:
        raise ValueError("请在设置中完整配置云存储的密钥及存储桶信息")

    # Extract & write local data.js
    data = extract_data(app)
    js_content = generate_js_data(data)
    
    # Store temporary data.js in app's appDataDir/scratch
    scratch_dir = Path(app.out_var.get() or INCOME_MEMORY_PATH.parent) / "temp_cloud"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    
    js_path = scratch_dir / "data.js"
    js_path.write_text(js_content, encoding="utf-8")

    # Locate index_template.html
    base_dir = Path(__file__).resolve().parent.parent
    html_template_path = base_dir / "gui_ctk" / "pages" / "index_template.html"
    
    # Upload files
    if provider == "cos":
        region = cfg.get("cloud_region", "").strip()
        if not region:
            raise ValueError("腾讯云 COS 必须配置 Region (如 ap-shanghai)")
        
        # Upload data.js
        upload_to_cos(js_path, "data.js", secret_id, secret_key, bucket, region)
        
        # Upload index.html if requested or doesn't exist
        if upload_html and html_template_path.exists():
            upload_to_cos(html_template_path, "index.html", secret_id, secret_key, bucket, region)
            
        url = cfg.get("cloud_url_path") or f"https://{bucket}.cos-website.{region}.myqcloud.com/index.html"
    
    elif provider == "oss":
        endpoint = cfg.get("cloud_endpoint", "").strip()
        if not endpoint:
            raise ValueError("阿里云 OSS 必须配置 Endpoint (如 oss-cn-hangzhou.aliyuncs.com)")
            
        # Upload data.js
        upload_to_oss(js_path, "data.js", secret_id, secret_key, bucket, endpoint)
        
        # Upload index.html if requested or doesn't exist
        if upload_html and html_template_path.exists():
            upload_to_oss(html_template_path, "index.html", secret_id, secret_key, bucket, endpoint)
            
        url = cfg.get("cloud_url_path") or f"https://{bucket}.{endpoint}/index.html"
        
    else:
        raise ValueError(f"不支持的云存储服务商: {provider}")

    return url
