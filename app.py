import os
import streamlit as st
import subprocess
import zipfile
import shutil
from pathlib import Path

# Установка конфигурации страницы
st.set_page_config(
    page_title="Magisk Boot Animation Generator",
    page_icon="🎬",
    layout="centered"
)

st.title("🎬 Конвертер видео в Magisk Boot Animation")
st.markdown(
    "Загрузите видеофайл (`.mp4`, `.mkv`), настройте параметры и скачайте готовый "
    "**Magisk / KernelSU модуль** для вашего Android-устройства!"
)

# Раздел настроек в сайдбаре
st.sidebar.header("⚙️ Параметры модуля")
module_name_input = st.sidebar.text_input("Название модуля (латиницей)", value="custom_video")
width = st.sidebar.text_input("Ширина экрана (px)", value="1080")
height = st.sidebar.text_input("Высота экрана (px)", value="2400")
fps = st.sidebar.slider("Количество кадров в секунду (FPS)", min_value=15, max_value=60, value=30, step=5)

# Основная область: загрузка файла
uploaded_file = st.file_uploader("Выберите видеофайл", type=["mp4", "mkv", "avi", "mov"])

if uploaded_file is not None:
    # Отображаем превью видео
    st.video(uploaded_file)
    
    if st.button("🚀 Собрать Magisk-модуль", type="primary", use_container_width=True):
        # Очистка имени модуля
        mod_name = module_name_input.strip().lower().replace(" ", "_")
        if not mod_name:
            mod_name = "custom_video_anim"
            
        if not width.isdigit() or not height.isdigit():
            st.error("Ошибка: Разрешение экрана должно содержать только цифры!")
            st.stop()

        # Создаем временную рабочую директорию
        work_dir = Path("temp_build")
        if work_dir.exists():
            shutil.rmtree(work_dir)
            
        part0_dir = work_dir / "part0"
        part0_dir.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем загруженное видео во временный файл
        temp_video_path = work_dir / uploaded_file.name
        with open(temp_video_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with st.status("🔄 Обработка видео...", expanded=True) as status:
            try:
                st.write("1/4 Нарезка видео на кадры через FFmpeg...")
                ffmpeg_cmd = [
                    "ffmpeg", "-y", "-i", str(temp_video_path),
                    "-vf", f"fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                    f"{part0_dir}/frame_%04d.png"
                ]
                subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

                st.write("2/4 Создание конфигурации desc.txt...")
                desc_content = f"{width} {height} {fps}\np 0 0 part0\n"
                with open(work_dir / "desc.txt", "w") as f:
                    f.write(desc_content)

                st.write("3/4 Упаковка в bootanimation.zip (без сжатия)...")
                bootanim_zip = work_dir / "bootanimation.zip"
                with zipfile.ZipFile(bootanim_zip, 'w', zipfile.ZIP_STORED) as zf:
                    zf.write(work_dir / "desc.txt", "desc.txt")
                    for img in sorted(part0_dir.glob("*.png")):
                        zf.write(img, f"part0/{img.name}")

                st.write("4/4 Сборка структуры Magisk-модуля...")
                module_root = work_dir / "module_structure"
                media_dir = module_root / "system" / "product" / "media"
                media_dir.mkdir(parents=True, exist_ok=True)
                
                shutil.move(bootanim_zip, media_dir / "bootanimation.zip")

                pretty_name = mod_name.replace("_", " ").title()
                prop_content = f"""id={mod_name}_bootanim
name=Video Boot Animation ({pretty_name})
version=1.0
versionCode=1
author=Tuxedo
description=Custom boot animation generated from video file via web converter.
"""
                with open(module_root / "module.prop", "w") as f:
                    f.write(prop_content)

                # Финальный архив
                output_dir = Path("dist")
                output_dir.mkdir(parents=True, exist_ok=True)
                final_zip_path = output_dir / f"{mod_name}_Magisk_Module.zip"
                
                with zipfile.ZipFile(final_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for root, dirs, files in os.walk(module_root):
                        for file in files:
                            full_path = Path(root) / file
                            arcname = full_path.relative_to(module_root)
                            zf.write(full_path, arcname)

                status.update(label="✅ Модуль успешно готов!", state="complete", expanded=False)
                
                # Кнопка скачивания готового архива
                with open(final_zip_path, "rb") as fp:
                    st.download_button(
                        label="📥 Скачать готовый Magisk-модуль (.zip)",
                        data=fp,
                        file_name=final_zip_path.name,
                        mime="application/zip",
                        type="primary",
                        use_container_width=True
                    )

            except Exception as e:
                status.update(label="❌ Ошибка при обработке видео", state="error")
                st.error(f"Подробности ошибки: {e}")
            finally:
                if temp_video_path.exists():
                    temp_video_path.unlink(missing_ok=True)