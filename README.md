# عارض مكتبة OfflineMaps

مشروع سطح مكتب بسيط لعرض صور الخرائط والمعاينات، وإدارة طبقات الصور والمعالم. واجهة البرنامج بالعربية.

> تنبيه: هذا ليس بديلاً كاملاً لتطبيق OfflineMaps. مخزن البلاطات `.DAT/.IDX` وبيانات الارتفاع `.AQE` بصيغ داخلية غير موثقة، ولا يستطيع هذا المشروع فكها. تفاصيل الميزات والقيود في [دليل المشروع العربي](README_AR.md).

## المتطلبات

- Windows 10 أو أحدث لبناء وتشغيل ملف EXE.
- Python 3.10 أو أحدث.
- Pillow (يُثبت من `requirements.txt`).

## تشغيل من المصدر

```powershell
py -m pip install -r requirements.txt
py map_viewer.py
```

اختر مجلد الصور/المعاينات من داخل التطبيق. بيانات الخرائط الخاصة بك لا ترفع إلى هذا المستودع.

## بناء تطبيق Windows

على Windows انقر مرتين على `build_windows.bat` أو شغّله من PowerShell. يظهر الناتج في `dist/OfflineMapsViewer.exe`. يمكن أيضاً تشغيل Workflow البناء من صفحة Actions في GitHub لتنزيل نسخة Windows.

## التنزيل والتحزيم

- تنزيل المشروع (ZIP): <https://github.com/samsms0002-gif/OfflineMapsViewer/archive/refs/heads/main.zip>
- استنساخ المستودع: `git clone https://github.com/samsms0002-gif/OfflineMapsViewer.git`
- تنزيل EXE جاهز: <https://github.com/samsms0002-gif/OfflineMapsViewer/releases/latest/download/OfflineMapsViewer.exe>
- أحدث إصدار: <https://github.com/samsms0002-gif/OfflineMapsViewer/releases/latest>
- التحزيم التلقائي (GitHub Actions): <https://github.com/samsms0002-gif/OfflineMapsViewer/actions/workflows/build-windows.yml>
- تنزيل من Artifacts: افتح آخر تشغيل ناجح في صفحة Actions ثم نزّل `OfflineMapsViewer-windows`.

## الميزات

- استعراض صور الخرائط والمعاينات وصور raster الشائعة.
- طبقات صور مع شفافية منفصلة، وتعديل التشبع والتباين.
- تحريك وتكبير، والانتقال إلى إحداثيات عشرية للصور ذات مرجع مكاني متاح.
- إنشاء نقاط وقياس المسافات؛ استيراد GPX/KML/KMZ وتصدير GPX/KML.
- حفظ جلسات العمل ومجموعات الخرائط المفضلة وتصدير صورة العرض.

## ملفات المشروع

- `map_viewer.py`: التطبيق.
- `requirements.txt`: اعتماديات Python.
- `build_windows.bat`: بناء EXE محلياً على Windows.
- `.github/workflows/build-windows.yml`: بناء Windows عبر GitHub Actions.
- `README_AR.md`: تحليل ملفات OfflineMaps وتفاصيل الاستخدام والقيود.

## الخصوصية وحجم البيانات

مجلد `files/` مستثنى من Git عمداً؛ قد يحتوي ملفات شخصية ومخازن خرائط كبيرة. لا تزل الاستثناء إلا إذا كنت تقصد نشر تلك البيانات ولديك حق مشاركتها.
