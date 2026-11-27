# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

"""Registry of visual templates: what each one needs (photos, fields) and how
to render it. The frontend builds its form directly from this registry, so
adding a template here is enough to make it selectable and configurable --
no parallel frontend field list to keep in sync.
"""
from scripts import image_templates as _img

TEMPLATES = [
    {
        "id": "quote_card",
        "name": "คำคมบนภาพ",
        "description": "ภาพพื้นหลัง + คำคม (อังกฤษ/ไทย) + เครดิต",
        "type": "image",
        "photos": [{"key": "photo", "label": "รูปพื้นหลัง"}],
        "fields": [
            {"key": "quote_en", "label": "คำคม (อังกฤษ)", "type": "text", "placeholder": "Let your past make you better"},
            {"key": "quote_th", "label": "คำแปลไทย", "type": "text", "placeholder": "ให้อดีตทำให้คุณเป็นคนที่ดีกว่าเดิม"},
            {"key": "credit", "label": "เครดิต/ชื่อผู้โพสต์", "type": "text", "placeholder": "ชื่อของคุณ"},
            {"key": "border_color", "label": "สีกรอบ", "type": "color", "default": "#8b3a2f"},
        ],
    },
    {
        "id": "before_after",
        "name": "ก่อน-หลัง",
        "description": "สองภาพสไตล์โพลารอยด์ซ้อนกัน พร้อมคำอธิบายแต่ละภาพ",
        "type": "image",
        "photos": [
            {"key": "photo_before", "label": "รูปก่อน"},
            {"key": "photo_after", "label": "รูปหลัง"},
        ],
        "fields": [
            {"key": "label_before", "label": "คำอธิบายรูปก่อน", "type": "text", "placeholder": "ตอนนั้น 12 ต.ค. 2022"},
            {"key": "label_after", "label": "คำอธิบายรูปหลัง", "type": "text", "placeholder": "ตอนนี้ 12 ต.ค. 2026"},
            {"key": "bg_color", "label": "สีพื้นหลัง", "type": "color", "default": "#c9bfa5"},
        ],
    },
    {
        "id": "framed_photo",
        "name": "กรอบรูปตกแต่ง",
        "description": "ภาพเดียวในกรอบวงรีหรือมุมโค้ง พร้อมขอบไล่สี",
        "type": "image",
        "photos": [{"key": "photo", "label": "รูปภาพ"}],
        "fields": [
            {"key": "shape", "label": "รูปทรงกรอบ", "type": "select", "default": "oval",
             "options": [{"value": "oval", "label": "วงรี"}, {"value": "rounded", "label": "สี่เหลี่ยมมุมโค้ง"}]},
            {"key": "frame_color1", "label": "สีกรอบ 1", "type": "color", "default": "#a7c7e7"},
            {"key": "frame_color2", "label": "สีกรอบ 2", "type": "color", "default": "#e7a7c9"},
            {"key": "bg_color", "label": "สีพื้นหลัง", "type": "color", "default": "#f3f1ec"},
        ],
    },
    {
        "id": "social_repost",
        "name": "โพสต์ข่าว/โซเชียล",
        "description": "หัวข้อข่าว + แถบช่อง (ชื่อ/เครื่องหมายยืนยัน) + ยอดไลค์-คอมเมนต์-แชร์ -- กรอกข้อมูลเองได้ทั้งหมด",
        "type": "both",  # image preview, and usable as a video overlay
        "photos": [{"key": "photo", "label": "ภาพ/ภาพตัวอย่างคลิป"}],
        "fields": [
            {"key": "headline", "label": "หัวข้อข่าว", "type": "textarea", "placeholder": "พาดหัวข่าวของคุณ"},
            {"key": "channel_name", "label": "ชื่อช่อง", "type": "text", "placeholder": "ชื่อช่องของคุณ"},
            {"key": "verified", "label": "แสดงเครื่องหมายยืนยันตัวตน", "type": "checkbox", "default": False},
            {"key": "like_count", "label": "ยอดไลค์", "type": "text", "placeholder": "1,568"},
            {"key": "comment_count", "label": "ยอดคอมเมนต์", "type": "text", "placeholder": "17"},
            {"key": "share_count", "label": "ยอดแชร์", "type": "text", "placeholder": "48"},
            {"key": "caption", "label": "คำบรรยายท้ายโพสต์", "type": "textarea", "placeholder": "คำบรรยายเพิ่มเติม..."},
        ],
    },
]

_BY_ID = {t["id"]: t for t in TEMPLATES}


def get_template(template_id: str) -> dict | None:
    return _BY_ID.get(template_id)


def list_templates() -> list[dict]:
    return TEMPLATES


def render_image_template(template_id: str, photo_paths: dict[str, str], fields: dict, out_path: str) -> str:
    """Dispatches to the matching scripts.image_templates.render_* function.

    `photo_paths` maps each template's declared photo key to a file path;
    `fields` maps each declared field key to its value (already the right
    type -- bool for checkboxes, str otherwise).
    """
    tpl = get_template(template_id)
    if not tpl:
        raise ValueError(f"Unknown template: {template_id}")

    if template_id == "quote_card":
        return _img.render_quote_card(
            photo_paths["photo"], out_path,
            quote_en=fields.get("quote_en", ""),
            quote_th=fields.get("quote_th", ""),
            credit=fields.get("credit", ""),
            border_color=fields.get("border_color") or "#8b3a2f",
        )
    if template_id == "before_after":
        return _img.render_before_after(
            photo_paths["photo_before"], photo_paths["photo_after"], out_path,
            label_before=fields.get("label_before", ""),
            label_after=fields.get("label_after", ""),
            bg_color=fields.get("bg_color") or "#c9bfa5",
        )
    if template_id == "framed_photo":
        return _img.render_framed_photo(
            photo_paths["photo"], out_path,
            shape=fields.get("shape") or "oval",
            frame_color1=fields.get("frame_color1") or "#a7c7e7",
            frame_color2=fields.get("frame_color2") or "#e7a7c9",
            bg_color=fields.get("bg_color") or "#f3f1ec",
        )
    if template_id == "social_repost":
        return _img.render_social_repost(
            photo_paths["photo"], out_path,
            headline=fields.get("headline", ""),
            channel_name=fields.get("channel_name", ""),
            verified=bool(fields.get("verified")),
            like_count=fields.get("like_count", ""),
            comment_count=fields.get("comment_count", ""),
            share_count=fields.get("share_count", ""),
            caption=fields.get("caption", ""),
        )

    raise ValueError(f"No renderer wired for template: {template_id}")
