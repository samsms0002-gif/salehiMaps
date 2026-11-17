"""salehiMaps viewer. Displays image previews and standard raster maps."""
from __future__ import annotations

import os
import math
import json
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from PIL import ImageEnhance

from PIL import Image, ImageTk


APP_TITLE = "salehiMaps"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
PREVIEW_EXT = ".PREVIEW"


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


class MapViewer:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1280x800")
        self.root.minsize(850, 550)
        self.root.configure(bg="#101923")
        self.root.option_add("*Font", "{Segoe UI} 10")
        self.map_root = tk.StringVar()
        self.status = tk.StringVar(value="اختر مجلد الخرائط أو افتح صورة خريطة")
        self.opacity = tk.DoubleVar(value=55)
        self.zoom = 1.0
        self.offset_x = self.offset_y = 0
        self.drag_start = None
        self.records: list[dict] = []
        self.visible: set[str] = set()
        self.landmarks: list[dict] = []
        self.mode = tk.StringVar(value="تحريك")
        self.measure_points: list[tuple[float, float]] = []
        self.saturation = tk.DoubleVar(value=1.0)
        self.contrast = tk.DoubleVar(value=1.0)
        self.favorites: dict[str, list[str]] = {}
        self.photo = None
        self._build_ui()
        self.root.bind("<Control-o>", lambda _e: self.choose_folder())
        self.root.bind("<Control-plus>", lambda _e: self.change_zoom(1.2))
        self.root.bind("<Control-minus>", lambda _e: self.change_zoom(1 / 1.2))
        self.root.bind("<Configure>", self._resize_event)
        self._autodetect()
        self.root.after(300, self._restore_favorites)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#101923")
        style.configure("Panel.TFrame", background="#182431")
        style.configure("TLabel", background="#182431", foreground="#e8f0f7")
        style.configure("Title.TLabel", background="#182431", foreground="#ffffff", font=("Segoe UI", 16, "bold"))
        style.configure("TButton", padding=7)
        style.configure("TCheckbutton", background="#182431", foreground="#e8f0f7")
        style.configure("Treeview", rowheight=28, background="#182431", fieldbackground="#182431", foreground="#e8f0f7")
        style.configure("Treeview.Heading", background="#26394b", foreground="white")

        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        toolbar = ttk.Frame(outer, style="Panel.TFrame", padding=8)
        toolbar.pack(fill="x", pady=(0, 9))
        ttk.Label(toolbar, text="salehiMaps", style="Title.TLabel").pack(side="right", padx=10)
        ttk.Button(toolbar, text="اختيار مجلد الخرائط", command=self.choose_folder).pack(side="right", padx=4)
        ttk.Button(toolbar, text="فتح صورة", command=self.open_image).pack(side="right", padx=4)
        ttk.Button(toolbar, text="انتقال إلى إحداثيات", command=self.goto_coordinates).pack(side="right", padx=4)
        ttk.Button(toolbar, text="استيراد GPX/KML", command=self.import_landmarks).pack(side="right", padx=4)
        ttk.Button(toolbar, text="تصدير المعالم", command=self.export_landmarks).pack(side="right", padx=4)
        ttk.Button(toolbar, text="حفظ جلسة", command=self.save_workspace).pack(side="right", padx=4)
        ttk.Button(toolbar, text="فتح جلسة", command=self.load_workspace).pack(side="right", padx=4)
        ttk.Button(toolbar, text="مساعدة", command=self.show_help).pack(side="right", padx=4)
        ttk.Button(toolbar, text="تصدير العرض", command=self.export_view).pack(side="left", padx=4)
        ttk.Button(toolbar, text="−", width=3, command=lambda: self.change_zoom(1/1.2)).pack(side="left", padx=2)
        ttk.Button(toolbar, text="+", width=3, command=lambda: self.change_zoom(1.2)).pack(side="left", padx=2)
        ttk.Button(toolbar, text="ملاءمة", command=self.fit_map).pack(side="left", padx=4)

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        side = ttk.Frame(body, style="Panel.TFrame", padding=10, width=330)
        side.pack(side="right", fill="y", padx=(9, 0))
        side.pack_propagate(False)
        ttk.Label(side, text="الخرائط والطبقات", style="Title.TLabel").pack(anchor="e", pady=(0, 8))
        self.folder_label = ttk.Label(side, text="لم يتم اختيار مجلد", wraplength=290)
        self.folder_label.pack(anchor="e", fill="x", pady=(0, 8))
        list_frame = ttk.Frame(side, style="Panel.TFrame")
        list_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(list_frame, columns=("size",), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="الصورة / الطبقة", anchor="e")
        self.tree.heading("size", text="الحجم", anchor="center")
        self.tree.column("#0", width=205, anchor="e")
        self.tree.column("size", width=75, anchor="center")
        self.tree.pack(side="right", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        self.tree.bind("<Double-1>", self._double_click)
        ttk.Label(side, text="شفافية الطبقة المحددة").pack(anchor="e", pady=(12, 2))
        self.opacity_scale = ttk.Scale(side, from_=0, to=100, variable=self.opacity, command=self._opacity_changed)
        self.opacity_scale.pack(fill="x")
        ttk.Label(side, text="اسحب للتنقل · عجلة الفأرة للتكبير").pack(anchor="e", pady=(10, 0))
        actions = ttk.Frame(side, style="Panel.TFrame")
        actions.pack(fill="x", pady=(12, 2))
        ttk.Button(actions, text="إضافة نقطة", command=lambda: self.mode.set("نقطة")).pack(side="right", padx=2)
        ttk.Button(actions, text="قياس مسافة", command=self.start_measure).pack(side="right", padx=2)
        ttk.Button(actions, text="مسح القياس", command=self.clear_measure).pack(side="right", padx=2)
        ttk.Button(actions, text="حفظ مفضلة", command=self.save_favorite).pack(side="right", padx=2)
        self.favorite_choice = tk.StringVar(value="")
        self.favorite_menu = ttk.Combobox(side, textvariable=self.favorite_choice, state="readonly", values=[], justify="right")
        self.favorite_menu.pack(fill="x", pady=(5, 0))
        self.favorite_menu.bind("<<ComboboxSelected>>", self.use_favorite)
        ttk.Label(side, text="التشبع").pack(anchor="e", pady=(9, 0))
        ttk.Scale(side, from_=0, to=2, variable=self.saturation, command=lambda _v: self._render()).pack(fill="x")
        ttk.Label(side, text="التباين").pack(anchor="e", pady=(5, 0))
        ttk.Scale(side, from_=0, to=2, variable=self.contrast, command=lambda _v: self._render()).pack(fill="x")

        self.canvas = tk.Canvas(body, bg="#0b1117", highlightthickness=0, cursor="fleur")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda _e: self.change_zoom(1.12))
        self.canvas.bind("<Button-5>", lambda _e: self.change_zoom(1 / 1.12))
        self.canvas.bind("<Double-Button-1>", lambda _e: self.fit_map())
        self.canvas.bind("<Button-3>", self._canvas_action)
        ttk.Label(outer, textvariable=self.status, anchor="e").pack(fill="x", pady=(6, 0))

    def _autodetect(self):
        base = Path(__file__).resolve().parent
        candidates = [base / "files" / "datastore" / "maps", base / "datastore" / "maps"]
        for path in candidates:
            if path.is_dir():
                self.map_root.set(str(path))
                self.scan_folder(path)
                return

    def choose_folder(self):
        path = filedialog.askdirectory(title="اختر مجلد الخرائط")
        if path:
            self.map_root.set(path)
            self.scan_folder(Path(path))

    def scan_folder(self, folder: Path):
        self.records.clear()
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() in IMAGE_EXTS or path.name.upper().endswith(PREVIEW_EXT):
                try:
                    with Image.open(path) as im:
                        im.verify()
                        self.records.append({"path": path, "name": path.name, "size": path.stat().st_size, "center": self._preview_center(path), "zoom": self._preview_zoom(path), "opacity":1.0})
                except Exception:
                    continue
        self.folder_label.configure(text=str(folder))
        self.visible.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, record in enumerate(self.records):
            iid = str(index)
            self.tree.insert("", "end", iid=iid, text=record["name"], values=(human_size(record["size"]),))
        # Default to the stored satellite map and overlay roads when present.
        base = next((i for i, r in enumerate(self.records) if r["name"].upper().endswith("GEARTH.PREVIEW")), None)
        if base is None and self.records:
            base = 0
        if base is not None:
            self.visible.add(str(base))
            roads = next((i for i, r in enumerate(self.records) if r["name"].upper().endswith("GROADS.PREVIEW")), None)
            if roads is not None:
                self.visible.add(str(roads))
                self.records[roads]["opacity"] = 0.55
                self.tree.selection_set(str(roads))
            else:
                self.tree.selection_set(str(base))
            self._render()
            self.root.after(100, self.fit_map)
        self.status.set(f"تم العثور على {len(self.records)} صورة/معاينة. ملفات DAT/IDX تُعرض كبيانات داخلية وليست صوراً مباشرة.")

    def open_image(self):
        filename = filedialog.askopenfilename(title="فتح صورة خريطة", filetypes=[("صور الخرائط", "*.jpg *.jpeg *.png *.bmp *.webp *.tif *.tiff"), ("كل الملفات", "*.*")])
        if filename:
            path = Path(filename)
            self.records.append({"path": path, "name": path.name, "size": path.stat().st_size, "center": self._worldfile_center(path), "zoom": 10, "opacity":1.0})
            iid = str(len(self.records) - 1)
            self.tree.insert("", "end", iid=iid, text=path.name, values=(human_size(path.stat().st_size),))
            self.visible = {iid}
            self.tree.selection_set(iid)
            self.fit_map()

    def _selection_changed(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        iid = selected[0]
        if iid not in self.visible:
            self.visible.add(iid)
            self.records[int(iid)]["opacity"] = 0.55
        self.opacity.set(float(self.records[int(iid)].get("opacity",1))*100)
        self._render()

    def _double_click(self, _event=None):
        selected = self.tree.selection()
        if selected:
            iid = selected[0]
            if iid in self.visible and len(self.visible) > 1:
                self.visible.remove(iid)
            else:
                self.visible.add(iid)
            self._render()

    def _opacity_changed(self, _value=None):
        selected=self.tree.selection()
        if selected:
            self.records[int(selected[0])]["opacity"]=self.opacity.get()/100
        self._render()

    def _compose(self):
        if not self.visible:
            return None
        ids = sorted(self.visible, key=lambda s: int(s))
        try:
            base = Image.open(self.records[int(ids[0])]["path"]).convert("RGBA")
            # Scale layer images to the base preview dimensions for a useful visual overlay.
            base_record = self.records[int(ids[0])]
            for iid in ids[1:]:
                record = self.records[int(iid)]
                layer = Image.open(record["path"]).convert("RGBA")
                # Align layers using their AQX preview-location values when available.
                if base_record.get("center") and record.get("center"):
                    layer = self._align_layer(layer, record, base.size, base_record)
                elif layer.size != base.size:
                    layer = layer.resize(base.size, Image.Resampling.LANCZOS)
                alpha = int(255 * float(record.get("opacity", self.opacity.get()/100)))
                layer.putalpha(layer.getchannel("A").point(lambda a: a * alpha // 255))
                base = Image.alpha_composite(base, layer)
            result = base.convert("RGB")
            result = ImageEnhance.Color(result).enhance(self.saturation.get())
            result = ImageEnhance.Contrast(result).enhance(self.contrast.get())
            return result
        except Exception as exc:
            self.status.set(f"تعذر فتح الصورة: {exc}")
            return None

    def _render(self):
        image = self._compose()
        if image is None:
            self.canvas.delete("all")
            return
        cw, ch = max(self.canvas.winfo_width(), 10), max(self.canvas.winfo_height(), 10)
        width, height = max(1, int(image.width * self.zoom)), max(1, int(image.height * self.zoom))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(cw / 2 + self.offset_x, ch / 2 + self.offset_y, image=self.photo, anchor="center")
        self.canvas.create_text(12, 12, text=f"{self.zoom * 100:.0f}%", fill="#ffffff", anchor="nw", font=("Segoe UI", 10, "bold"))
        self._draw_overlays(cw, ch)
        center = self._screen_to_geo(cw / 2, ch / 2)
        if center:
            self.canvas.create_text(12, 34, text=f"{center[0]:.5f}°, {center[1]:.5f}°  |  مقياس عرض تقريبي", fill="#ffffff", anchor="nw", font=("Segoe UI", 10))

    def fit_map(self):
        image = self._compose()
        if image is None:
            return
        cw, ch = max(self.canvas.winfo_width(), 10), max(self.canvas.winfo_height(), 10)
        self.zoom = min(cw / image.width, ch / image.height, 12)
        self.offset_x = self.offset_y = 0
        self._render()

    def change_zoom(self, factor):
        self.zoom = min(12, max(.08, self.zoom * factor))
        self._render()

    def _wheel(self, event):
        self.change_zoom(1.12 if event.delta > 0 else 1 / 1.12)

    def _start_drag(self, event):
        if self.mode.get() != "تحريك":
            self._canvas_action(event)
            return
        self.drag_start = (event.x, event.y, self.offset_x, self.offset_y)

    def _drag(self, event):
        if self.drag_start:
            x, y, ox, oy = self.drag_start
            self.offset_x, self.offset_y = ox + event.x - x, oy + event.y - y
            self._render()

    def _resize_event(self, event):
        if event.widget == self.root:
            self.root.after_idle(self._render)

    def export_view(self):
        image = self._compose()
        if image is None:
            messagebox.showinfo(APP_TITLE, "اختر خريطة أولاً")
            return
        filename = filedialog.asksaveasfilename(title="تصدير صورة الخريطة", defaultextension=".png", filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if filename:
            image.save(filename)
            self.status.set(f"تم حفظ الصورة: {filename}")

    def save_workspace(self):
        filename=filedialog.asksaveasfilename(title="حفظ جلسة العمل",defaultextension=".omw",filetypes=[("salehiMaps Workspace","*.omw"),("JSON","*.json")])
        if not filename: return
        state={"version":1,"folder":self.map_root.get(),"visible":[self.records[int(i)]["name"] for i in self.visible if int(i)<len(self.records)],"zoom":self.zoom,"offset":[self.offset_x,self.offset_y],"landmarks":self.landmarks}
        Path(filename).write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
        self.status.set(f"تم حفظ جلسة العمل: {filename}")

    def load_workspace(self):
        filename=filedialog.askopenfilename(title="فتح جلسة عمل",filetypes=[("salehiMaps Workspace","*.omw *.json"),("كل الملفات","*.*")])
        if not filename: return
        try:
            state=json.loads(Path(filename).read_text(encoding="utf-8")); folder=Path(state.get("folder",""))
            if folder.is_dir(): self.map_root.set(str(folder)); self.scan_folder(folder)
            self.visible={str(i) for i,r in enumerate(self.records) if r["name"] in state.get("visible",[])}
            if not self.visible and self.records: self.visible={"0"}
            self.zoom=float(state.get("zoom",1)); self.offset_x,self.offset_y=state.get("offset",[0,0]); self.landmarks=state.get("landmarks",[])
            self._render(); self.status.set("تمت استعادة جلسة العمل")
        except Exception as exc: messagebox.showerror(APP_TITLE,f"تعذر فتح جلسة العمل: {exc}")

    def _favorite_file(self):
        path=Path.home()/".salehimaps"/"favorites.json"; path.parent.mkdir(parents=True,exist_ok=True); return path

    def _restore_favorites(self):
        try: self.favorites=json.loads(self._favorite_file().read_text(encoding="utf-8"))
        except Exception: self.favorites={}
        self.favorite_menu["values"]=list(self.favorites)

    def save_favorite(self):
        name=simpledialog.askstring("مجموعة خرائط مفضلة","اسم المجموعة:")
        if not name: return
        self.favorites[name]=[self.records[int(i)]["name"] for i in self.visible if int(i)<len(self.records)]
        try:
            self._favorite_file().write_text(json.dumps(self.favorites,ensure_ascii=False,indent=2),encoding="utf-8")
            self.favorite_menu["values"]=list(self.favorites); self.favorite_choice.set(name); self.status.set(f"حفظت مجموعة الخرائط: {name}")
        except Exception as exc: messagebox.showerror(APP_TITLE,f"تعذر حفظ المجموعة: {exc}")

    def use_favorite(self,_event=None):
        names=self.favorites.get(self.favorite_choice.get(),[])
        self.visible={str(i) for i,r in enumerate(self.records) if r["name"] in names}
        self._render(); self.status.set(f"تم عرض المجموعة: {self.favorite_choice.get()}")

    def show_help(self):
        text=("دليل سريع\n\n"
              "• اختر مجلد datastore/maps لعرض معاينات AQX وصور الخرائط القياسية.\n"
              "• انقر على طبقة لإضافتها؛ انقر مرتين لإظهارها أو إخفائها. منزلق الشفافية يتحكم بطبقة الاختيار فقط.\n"
              "• اسحب للتحريك، عجلة الفأرة للتكبير، وملاءمة لإظهار الصورة كاملة.\n"
              "• انتقال إلى إحداثيات يقبل خط العرض، خط الطول بصيغة عشرية.\n"
              "• إضافة نقطة ثم النقر على الخريطة ينشئ معلمًا؛ استيراد/تصدير يدعم GPX وKML، والاستيراد يقبل KMZ.\n"
              "• قياس المسافة يجمع نقاطًا بالنقر؛ النتائج على صور AQX تقريبية.\n"
              "• يمكن تعديل التشبع والتباين، وتصدير صورة العرض، وحفظ جلسات عمل ومجموعات خرائط مفضلة.\n\n"
              "المعايرة: معاينات AQX تستخدم إحداثيات preview-location من ملف AQX. الصور الأخرى تحتاج ملف world file مثل .jgw أو .pgw.\n"
              "القيود الحالية: ملفات DAT/IDX وDEM الخاصة غير مفكوكة؛ لا يوجد GPS/بوصلة أو تنزيل بلاطات أو بحث أسماء أماكن أو تحليل ارتفاعات.\n\n"
              "المساعدة الرسمية للتطبيق: https://www.offline-maps.net/en/help")
        messagebox.showinfo("مساعدة salehiMaps",text)

    # Preview positions in AQX are latitude,longitude,zoom. This is a display
    # reference, not a claim that the proprietary cache has been georeferenced.
    def _preview_center(self, path):
        if not path.name.upper().endswith(".PREVIEW"):
            return self._worldfile_center(path)
        parent = path.parent
        for aqx in parent.glob("*.AQX"):
            try:
                root = ET.parse(aqx).getroot()
                for source in root.findall(".//source"):
                    preview = (source.findtext("preview-url") or "").split("preview/")[-1]
                    sourceid = source.attrib.get("id", "")
                    if path.name.upper() in (preview.upper(), (aqx.name + "." + sourceid + ".PREVIEW").upper()):
                        value = source.findtext("preview-location")
                        if value:
                            lat, lon, *_ = [float(v) for v in value.split(",")]
                            return lat, lon
                # Most local previews are named <AQX>.<SOURCE>.PREVIEW.
                stem = path.name.upper().removesuffix(".PREVIEW")
                sourceid = stem.split(".")[-1]
                source = root.find(f".//source[@id='{sourceid}']")
                if source is not None and source.findtext("preview-location"):
                    lat, lon, *_ = [float(v) for v in source.findtext("preview-location").split(",")]
                    return lat, lon
            except Exception:
                pass
        return None

    def _preview_zoom(self, path):
        if not path.name.upper().endswith(".PREVIEW"):
            return 10
        sourceid = path.name.upper().removesuffix(".PREVIEW").split(".")[-1]
        for aqx in path.parent.glob("*.AQX"):
            try:
                root=ET.parse(aqx).getroot(); source=root.find(f".//source[@id='{sourceid}']")
                vals=(source.findtext("preview-location") if source is not None else "").split(",")
                if len(vals)>2: return int(float(vals[2]))
            except Exception: pass
        return 10

    def _worldfile_center(self, path):
        for ext in (".wld", ".jgw", ".pgw", ".tfw", ".jgwx", ".pgwx", ".tfwx"):
            wf = path.with_suffix(ext)
            if wf.exists():
                try:
                    a, d, b, e, c, f = [float(x.strip()) for x in wf.read_text().splitlines()[:6]]
                    with Image.open(path) as im:
                        x, y = im.width / 2, im.height / 2
                    return f + d * x + e * y, c + a * x + b * y
                except Exception:
                    return None
        return None

    @staticmethod
    def _mercator(lat, lon, zoom):
        size = 256 * 2**zoom
        lat = max(-85.0511, min(85.0511, lat))
        x = (lon + 180) / 360 * size
        sinlat = math.sin(math.radians(lat))
        y = (0.5 - math.log((1 + sinlat) / (1 - sinlat)) / (4 * math.pi)) * size
        return x, y

    @staticmethod
    def _inverse_mercator(x, y, zoom):
        size = 256 * 2**zoom
        lon = x / size * 360 - 180
        n = math.pi - 2 * math.pi * y / size
        lat = math.degrees(math.atan(math.sinh(n)))
        return lat, lon

    def _geo_per_pixel(self):
        if not self.visible:
            return None
        record = self.records[int(sorted(self.visible, key=int)[0])]
        if not record.get("center"):
            return None
        try:
            image = Image.open(record["path"])
            return record, image.size
        except Exception:
            return None

    def _screen_to_geo(self, sx, sy):
        info = self._geo_per_pixel()
        if not info:
            return None
        record, dims = info
        lat, lon = record["center"]
        z = record.get("zoom", 10)
        cx, cy = self._mercator(lat, lon, z)
        # Map image center is the AQX preview location; view zoom is relative.
        scale = self.zoom
        ix = (sx - self.canvas.winfo_width() / 2 - self.offset_x) / scale + dims[0] / 2
        iy = (sy - self.canvas.winfo_height() / 2 - self.offset_y) / scale + dims[1] / 2
        px = cx + ix - dims[0] / 2
        py = cy + iy - dims[1] / 2
        return self._inverse_mercator(px, py, z)

    def _geo_to_screen(self, lat, lon):
        info = self._geo_per_pixel()
        if not info:
            return None
        record, dims = info
        if not record.get("center"):
            return None
        z = record.get("zoom", 10)
        cx, cy = self._mercator(*record["center"], z)
        x, y = self._mercator(lat, lon, z)
        sx = self.canvas.winfo_width()/2 + self.offset_x + (x-cx)*self.zoom
        sy = self.canvas.winfo_height()/2 + self.offset_y + (y-cy)*self.zoom
        return sx, sy

    def _align_layer(self, image, record, target_size, base_record):
        try:
            z = base_record.get("zoom", 10)
            px, py = self._mercator(*record["center"], z)
            bx, by = self._mercator(*base_record["center"], z)
            factor = 2 ** (z - record.get("zoom", z))
            image = image.resize((max(1, round(image.width*factor)), max(1, round(image.height*factor))), Image.Resampling.LANCZOS)
            x = round(target_size[0]/2 + (px-bx) - image.width/2)
            y = round(target_size[1]/2 + (py-by) - image.height/2)
            layer = Image.new("RGBA", target_size)
            layer.alpha_composite(image, (x, y))
            return layer
        except Exception:
            return image.resize(target_size, Image.Resampling.LANCZOS)

    def _canvas_action(self, event):
        geo = self._screen_to_geo(event.x, event.y)
        if not geo:
            messagebox.showinfo(APP_TITLE, "الصورة الحالية لا تحتوي على مرجع جغرافي معروف. افتح صورة مصحوبة بملف world file أو معاينة AQX.")
            return
        if self.mode.get() == "نقطة":
            name = simpledialog.askstring("نقطة جديدة", "اسم المعلم:", initialvalue="نقطة جديدة")
            if name:
                self.landmarks.append({"name": name, "type": "wpt", "points": [geo]})
                self.mode.set("تحريك")
                self._render()
        elif self.mode.get() == "قياس":
            self.measure_points.append(geo)
            if len(self.measure_points) >= 2:
                dist = self._distance_km(*self.measure_points[-2], *self.measure_points[-1])
                self.status.set(f"المسافة بين آخر نقطتين: {dist:.2f} كم · القياس الجغرافي تقريبي للمعاينات")
            self._render()

    @staticmethod
    def _distance_km(lat1, lon1, lat2, lon2):
        r = 6371.0088
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
        a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return 2*r*math.asin(math.sqrt(a))

    def _draw_overlays(self, cw, ch):
        for item in self.landmarks:
            points = [self._geo_to_screen(*p) for p in item["points"]]
            points = [p for p in points if p]
            if item["type"] == "wpt" and points:
                x, y = points[0]
                self.canvas.create_oval(x-5,y-5,x+5,y+5,fill="#ffcc33",outline="#1b1b1b",width=2)
                self.canvas.create_text(x+8,y-8,text=item["name"],fill="white",anchor="sw")
            elif len(points) > 1:
                self.canvas.create_line(*[v for p in points for v in p],fill="#ff3b30",width=3)
        if len(self.measure_points) > 1:
            points = [self._geo_to_screen(*p) for p in self.measure_points]
            points = [p for p in points if p]
            if len(points) > 1:
                self.canvas.create_line(*[v for p in points for v in p],fill="#35d07f",width=2,dash=(5,3))
        self.canvas.create_line(cw/2-8,ch/2,cw/2+8,ch/2,fill="#ffffff",width=1)
        self.canvas.create_line(cw/2,ch/2-8,cw/2,ch/2+8,fill="#ffffff",width=1)

    def goto_coordinates(self):
        text = simpledialog.askstring("انتقال إلى إحداثيات", "أدخل خط العرض، خط الطول (مثال: 24.7, 46.7):")
        if not text:
            return
        try:
            lat, lon = [float(v.strip()) for v in text.replace(";", ",").split(",", 1)]
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("النطاق خارج الحدود")
            info = self._geo_per_pixel()
            if not info:
                messagebox.showinfo(APP_TITLE, "يلزم وجود خريطة ذات مرجع جغرافي للانتقال الدقيق.")
                return
            record, _dims = info
            z = record.get("zoom", 10)
            ax, ay = self._mercator(*record["center"], z)
            bx, by = self._mercator(lat, lon, z)
            self.offset_x = -(bx-ax)*self.zoom
            self.offset_y = -(by-ay)*self.zoom
            self._render()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"صيغة الإحداثيات غير صحيحة: {exc}")

    def start_measure(self):
        self.measure_points.clear()
        self.mode.set("قياس")
        self.status.set("انقر على نقطتين أو أكثر في الخريطة لحساب المسافة")

    def clear_measure(self):
        self.measure_points.clear()
        self.mode.set("تحريك")
        self._render()

    def import_landmarks(self):
        filename = filedialog.askopenfilename(title="استيراد المعالم", filetypes=[("GPX/KML/KMZ", "*.gpx *.kml *.kmz"), ("كل الملفات", "*.*")])
        if not filename:
            return
        try:
            path = Path(filename)
            if path.suffix.lower() == ".kmz":
                with ZipFile(path) as zf:
                    payload = zf.read(next(n for n in zf.namelist() if n.lower().endswith(".kml")))
            else:
                payload = path.read_bytes()
            root = ET.fromstring(payload)
            added = 0
            for el in root.iter():
                tag = el.tag.split("}")[-1].lower()
                if tag == "wpt":
                    self.landmarks.append({"name": el.attrib.get("name", "Waypoint"), "type": "wpt", "points": [(float(el.attrib["lat"]), float(el.attrib["lon"]))]}); added += 1
                elif tag in ("trkseg", "rte"):
                    coords = []
                    for p in el:
                        ptag = p.tag.split("}")[-1].lower()
                        if ptag in ("trkpt", "rtept"):
                            coords.append((float(p.attrib["lat"]), float(p.attrib["lon"])))
                    if len(coords) >= 2:
                        self.landmarks.append({"name": "مسار مستورد", "type": "rte", "points": coords}); added += 1
                elif tag == "placemark":
                    name = next((c.text for c in el if c.tag.split("}")[-1].lower()=="name" and c.text), "معلم مستورد")
                    for c in el.iter():
                        if c.tag.split("}")[-1].lower() == "coordinates" and c.text:
                            coords = []
                            for tuple_text in c.text.split():
                                vals = tuple_text.split(",")
                                if len(vals) >= 2: coords.append((float(vals[1]), float(vals[0])))
                            if coords: self.landmarks.append({"name":name,"type":"wpt" if len(coords)==1 else "rte","points":coords}); added += 1
            self._render()
            self.status.set(f"استوردت {added} معلم/مسار")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"تعذر استيراد الملف: {exc}")

    def export_landmarks(self):
        if not self.landmarks:
            messagebox.showinfo(APP_TITLE, "لا توجد معالم لتصديرها")
            return
        filename = filedialog.asksaveasfilename(title="تصدير المعالم", defaultextension=".gpx", filetypes=[("GPX", "*.gpx"), ("KML", "*.kml")])
        if not filename: return
        root = ET.Element("gpx", {"version":"1.1","creator":"salehiMaps","xmlns":"http://www.topografix.com/GPX/1/1"})
        for item in self.landmarks:
            if item["type"] == "wpt":
                lat,lon=item["points"][0]; w=ET.SubElement(root,"wpt",{"lat":str(lat),"lon":str(lon)}); ET.SubElement(w,"name").text=item["name"]
            else:
                trk=ET.SubElement(root,"trk"); ET.SubElement(trk,"name").text=item["name"]; seg=ET.SubElement(trk,"trkseg")
                for lat,lon in item["points"]: ET.SubElement(seg,"trkpt",{"lat":str(lat),"lon":str(lon)})
        payload=ET.tostring(root,encoding="utf-8",xml_declaration=True)
        if Path(filename).suffix.lower()==".kml":
            kroot=ET.Element("kml",{"xmlns":"http://www.opengis.net/kml/2.2"}); doc=ET.SubElement(kroot,"Document")
            for item in self.landmarks:
                pm=ET.SubElement(doc,"Placemark"); ET.SubElement(pm,"name").text=item["name"]
                coords=" ".join(f"{lon},{lat},0" for lat,lon in item["points"])
                geom=ET.SubElement(pm,"Point" if item["type"]=="wpt" else "LineString"); ET.SubElement(geom,"coordinates").text=coords
            payload=ET.tostring(kroot,encoding="utf-8",xml_declaration=True)
        Path(filename).write_bytes(payload)
        self.status.set(f"تم تصدير {len(self.landmarks)} معلم")


if __name__ == "__main__":
    root = tk.Tk()
    MapViewer(root)
    root.mainloop()
