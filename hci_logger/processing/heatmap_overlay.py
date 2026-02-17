# -*- coding: utf-8 -*-
"""Generador de heatmaps overlay sobre screenshots"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import gaussian_filter
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageDraw
import matplotlib.patches as patches


class HeatmapOverlayGenerator:
    """
    Genera heatmaps superpuestos sobre screenshots

    Esto permite visualizar la actividad del mouse sobre
    el contexto visual real de la aplicación/sitio web
    """

    def __init__(self, screen_width: int = 2880, screen_height: int = 1800):
        self.screen_width = screen_width
        self.screen_height = screen_height

    def generate_overlay_for_screenshot(
        self,
        screenshot_path: Path,
        events: List[Dict[str, Any]],
        output_path: Path,
        time_window: float = 5.0,
        blur_radius: int = 30,
        alpha: float = 0.6,
        show_clicks: bool = True,
        click_radius: int = 15
    ):
        """
        Genera heatmap overlay sobre un screenshot específico

        Args:
            screenshot_path: Ruta al screenshot base
            events: Lista de eventos de mouse a visualizar
            output_path: Ruta donde guardar la imagen resultante
            time_window: Ventana temporal (segundos) de eventos antes del screenshot
            blur_radius: Radio del gaussian blur para el heatmap
            alpha: Transparencia del heatmap (0.0 = transparente, 1.0 = opaco)
            show_clicks: Si mostrar marcadores visuales en los clicks
            click_radius: Radio de los círculos de click
        """
        if not screenshot_path.exists():
            print(f"⚠️  Screenshot no encontrado: {screenshot_path}")
            return False

        if not events:
            print(f"⚠️  No hay eventos para visualizar")
            return False

        try:
            # 1. Cargar screenshot base
            screenshot_img = Image.open(screenshot_path)
            screenshot_array = np.array(screenshot_img)

            # 2. Extraer coordenadas de eventos
            move_coords = []
            click_coords = []

            for event in events:
                x, y = event['x'], event['y']

                if event['event_type'] == 'move':
                    move_coords.append((x, y))
                elif event['event_type'] == 'click' and event.get('pressed'):
                    click_coords.append((x, y))
                    # También incluir clicks en el heatmap de movimientos
                    move_coords.append((x, y))

            # 3. Crear heatmap de actividad
            if move_coords:
                heatmap_array = self._create_heatmap_array(
                    coordinates=move_coords,
                    blur_radius=blur_radius
                )
            else:
                heatmap_array = np.zeros((self.screen_height, self.screen_width))

            # 4. Crear figura para overlay
            fig, ax = plt.subplots(figsize=(16, 10), dpi=150)

            # Mostrar screenshot base
            ax.imshow(screenshot_array, extent=[0, self.screen_width, self.screen_height, 0])

            # 5. Overlay del heatmap con transparencia
            if heatmap_array.max() > 0:
                # Colormap personalizado (azul -> verde -> amarillo -> rojo)
                colors = ['#00000000', '#0000FF', '#00FF00', '#FFFF00', '#FF0000']
                cmap = LinearSegmentedColormap.from_list('heatmap_overlay', colors, N=100)

                # Aplicar heatmap con alpha
                heatmap_overlay = ax.imshow(
                    heatmap_array,
                    cmap=cmap,
                    interpolation='bilinear',
                    alpha=alpha,
                    extent=[0, self.screen_width, self.screen_height, 0]
                )

                # Añadir colorbar
                cbar = plt.colorbar(heatmap_overlay, ax=ax, fraction=0.046, pad=0.04)
                cbar.set_label('Intensidad de Actividad', rotation=270, labelpad=20)

            # 6. Marcar clicks con círculos
            if show_clicks and click_coords:
                for x, y in click_coords:
                    # Círculo rojo semi-transparente
                    circle = patches.Circle(
                        (x, y),
                        radius=click_radius,
                        linewidth=2,
                        edgecolor='red',
                        facecolor='red',
                        alpha=0.4
                    )
                    ax.add_patch(circle)

                    # Borde blanco para mejor visibilidad
                    circle_outline = patches.Circle(
                        (x, y),
                        radius=click_radius,
                        linewidth=3,
                        edgecolor='white',
                        facecolor='none',
                        alpha=0.8
                    )
                    ax.add_patch(circle_outline)

            # 7. Configurar ejes
            ax.set_xlim(0, self.screen_width)
            ax.set_ylim(self.screen_height, 0)
            ax.axis('off')  # Sin ejes para una visualización más limpia

            # Título con info
            title = f"Heatmap Overlay - {len(move_coords)} movimientos"
            if click_coords:
                title += f" - {len(click_coords)} clicks"
            ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

            # 8. Guardar
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
            plt.close()

            return True

        except Exception as e:
            print(f"❌ Error generando overlay: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_all_overlays(
        self,
        screenshots: List[Dict[str, Any]],
        all_events: List[Dict[str, Any]],
        output_dir: Path,
        time_window: float = 5.0,
        **kwargs
    ) -> List[Path]:
        """
        Genera overlays para todos los screenshots

        Args:
            screenshots: Lista de screenshots (de la DB)
            all_events: Todos los eventos de mouse de la sesión
            output_dir: Directorio donde guardar los overlays
            time_window: Ventana temporal para eventos (segundos antes del screenshot)
            **kwargs: Argumentos adicionales para generate_overlay_for_screenshot

        Returns:
            Lista de rutas a los overlays generados
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        generated_overlays = []

        print(f"\n🎨 Generando {len(screenshots)} heatmap overlays...")

        for i, screenshot in enumerate(screenshots, 1):
            screenshot_path = Path(screenshot['file_path'])
            screenshot_time = screenshot['timestamp']

            # Filtrar eventos en la ventana temporal
            # Eventos desde (screenshot_time - time_window) hasta screenshot_time
            events_in_window = [
                e for e in all_events
                if (screenshot_time - time_window) <= e['timestamp'] <= screenshot_time
            ]

            # Nombre del archivo overlay
            screenshot_filename = screenshot_path.stem
            overlay_filename = f"overlay_{screenshot_filename}.png"
            overlay_path = output_dir / overlay_filename

            # Generar overlay
            print(f"  [{i}/{len(screenshots)}] {screenshot_filename}... ", end="", flush=True)

            success = self.generate_overlay_for_screenshot(
                screenshot_path=screenshot_path,
                events=events_in_window,
                output_path=overlay_path,
                time_window=time_window,
                **kwargs
            )

            if success:
                print(f"✓ ({len(events_in_window)} eventos)")
                generated_overlays.append(overlay_path)
            else:
                print(f"✗")

        print(f"\n✓ {len(generated_overlays)}/{len(screenshots)} overlays generados")
        return generated_overlays

    def _create_heatmap_array(
        self,
        coordinates: List[Tuple[int, int]],
        blur_radius: int
    ) -> np.ndarray:
        """
        Crea array 2D del heatmap

        Args:
            coordinates: Lista de tuplas (x, y)
            blur_radius: Radio del gaussian blur

        Returns:
            Array 2D normalizado del heatmap
        """
        heatmap = np.zeros((self.screen_height, self.screen_width))

        for x, y in coordinates:
            # Asegurar que las coordenadas están dentro de los límites
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))
            heatmap[y, x] += 1

        # Aplicar gaussian blur
        heatmap_blurred = gaussian_filter(heatmap, sigma=blur_radius)

        # Normalizar
        if heatmap_blurred.max() > 0:
            heatmap_blurred = heatmap_blurred / heatmap_blurred.max()

        return heatmap_blurred

    def create_comparison_grid(
        self,
        screenshots: List[Dict[str, Any]],
        overlay_paths: List[Path],
        output_path: Path,
        max_per_row: int = 3
    ):
        """
        Crea una grilla de comparación: screenshots originales vs overlays

        Args:
            screenshots: Lista de screenshots
            overlay_paths: Lista de rutas a overlays generados
            output_path: Ruta donde guardar la grilla
            max_per_row: Máximo de imágenes por fila
        """
        n_screenshots = len(screenshots)
        n_rows = (n_screenshots + max_per_row - 1) // max_per_row

        fig, axes = plt.subplots(
            n_rows,
            max_per_row * 2,  # 2 columnas por screenshot (original + overlay)
            figsize=(max_per_row * 8, n_rows * 5)
        )

        # Asegurar que axes sea un array 2D
        if n_rows == 1:
            axes = axes.reshape(1, -1)

        for i, (screenshot, overlay_path) in enumerate(zip(screenshots, overlay_paths)):
            row = i // max_per_row
            col_base = (i % max_per_row) * 2

            # Cargar imágenes
            screenshot_img = Image.open(screenshot['file_path'])
            overlay_img = Image.open(overlay_path)

            # Mostrar screenshot original
            axes[row, col_base].imshow(screenshot_img)
            axes[row, col_base].set_title(f"Screenshot #{i+1}\nOriginal", fontsize=10)
            axes[row, col_base].axis('off')

            # Mostrar overlay
            axes[row, col_base + 1].imshow(overlay_img)
            axes[row, col_base + 1].set_title(f"Screenshot #{i+1}\ncon Heatmap", fontsize=10)
            axes[row, col_base + 1].axis('off')

        # Ocultar axes vacíos
        for i in range(n_screenshots, n_rows * max_per_row):
            row = i // max_per_row
            col_base = (i % max_per_row) * 2
            axes[row, col_base].axis('off')
            axes[row, col_base + 1].axis('off')

        plt.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        plt.close()

        print(f"✓ Grilla de comparación generada: {output_path}")
