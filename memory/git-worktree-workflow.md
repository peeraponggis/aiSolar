---
name: git-worktree-workflow
description: หลักการทำงานงานเขียนโค้ด/สร้างคลิปสั้น — 1 Task = 1 Branch = 1 Worktree = 1 PR
metadata:
  type: feedback
---

สำหรับงาน **เขียนโค้ด** และ **สร้างคลิปสั้น** ทุกงาน ให้ยึดสถาปัตยกรรม:

> **1 Task = 1 Branch = 1 Worktree = 1 PR**

- **1 Task** — งานย่อยหนึ่งเรื่องจบในตัว (1 ฟีเจอร์ / 1 บั๊ก / 1 คลิป)
- **1 Branch** — แตก branch ใหม่ต่อ task เสมอ ห้ามทำงานบน main/master โดยตรง
- **1 Worktree** — ใช้ `git worktree` แยกโฟลเดอร์ทำงานต่อ branch เพื่อทำหลาย task ขนานกันได้โดยไม่สลับ branch (เหมาะกับหลาย agent ทำพร้อมกัน)
- **1 PR** — แต่ละ task ปิดด้วย Pull Request เดียว รีวิว/merge แล้วลบ branch + worktree

**Why:** ผู้ใช้กำหนดหลักการนี้เป็นมาตรฐานการทำงานของโปรเจกต์ ให้แยกงานชัดเจน ตรวจสอบย้อนกลับได้ และรองรับการทำงานขนาน

**How to apply:** เมื่อเริ่ม task ใหม่ ให้เสนอ/ใช้ `git worktree add ../work-<task> -b <type>/<task>` ทำงานในโฟลเดอร์นั้น จบด้วย PR เดียว หลัง merge แล้ว `git worktree remove`. ผูกกับข้อบังคับ [[no-code-on-c-drive]]
