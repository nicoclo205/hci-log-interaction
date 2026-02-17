# -*- coding: utf-8 -*-
"""Generador de heatmaps a partir de eventos de mouse"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import gaussian_filter
from pathlib import Path
from typing import List, Dict, Any, Tuple


class HeatmapGenerator:
    """Genera heatmaps visuales de interacciones del mouse"""

    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        self.screen_width = screen_width
        self.screen_height = screen_height

    def generate_from_events(
        self,
        events: List[Dict[str, Any]],
        output_path: Path,
        blur_radius: int = 20,
        event_types: List[str] = None
    ):
        """
        Genera heatmap a partir de lista de eventos

        Args:
            events: Lista de eventos de mouse
            output_path: Ruta donde guardar la imagen
            blur_radius: Radio del gaussian blur (más alto = más suave)
            event_types: Tipos de eventos a incluir (default: ['move', 'click'])
        """
        if event_types is None:
            event_types = ['move', 'click']

        # Filtrar eventos por tipo
        filtered_events = [
            e for e in events
            if e.get('event_type') in event_types
        ]

        if not filtered_events:
            print("⚠️  No hay eventos para generar heatmap")
            return

        # Extraer coordenadas
        coordinates = [(e['x'], e['y']) for e in filtered_events]

        # Generar heatmap
        self._generate_heatmap_image(
            coordinates=coordinates,
            output_path=output_path,
            blur_radius=blur_radius,
            title=f"Heatmap - {len(filtered_events)} eventos"
        )

        print(f"✓ Heatmap generado: {output_path}")

    def generate_click_heatmap(
        self,
        events: List[Dict[str, Any]],
        output_path: Path,
        blur_radius: int = 30
    ):
        """Genera heatmap solo de clicks"""
        click_events = [
            e for e in events
            if e.get('event_type') == 'click' and e.get('pressed') is True
        ]

        if not click_events:
            print("⚠️  No hay clicks para generar heatmap")
            return

        coordinates = [(e['x'], e['y']) for e in click_events]

        self._generate_heatmap_image(
            coordinates=coordinates,
            output_path=output_path,
            blur_radius=blur_radius,
            title=f"Click Heatmap - {len(click_events)} clicks"
        )

        print(f"✓ Click heatmap generado: {output_path}")

    def _generate_heatmap_image(
        self,
        coordinates: List[Tuple[int, int]],
        output_path: Path,
        blur_radius: int,
        title: str
    ):
        """Genera la imagen del heatmap"""
        # Crear matriz 2D para acumular eventos
        heatmap = np.zeros((self.screen_height, self.screen_width))

        # Acumular eventos en la matriz
        for x, y in coordinates:
            # Asegurar que las coordenadas están dentro de los límites
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))
            heatmap[y, x] += 1

        # Aplicar gaussian blur para suavizar
        heatmap_blurred = gaussian_filter(heatmap, sigma=blur_radius)

        # Normalizar
        if heatmap_blurred.max() > 0:
            heatmap_blurred = heatmap_blurred / heatmap_blurred.max()

        # Crear colormap personalizado (azul -> verde -> amarillo -> rojo)
        colors = ['#000033', '#0000FF', '#00FF00', '#FFFF00', '#FF0000']
        n_bins = 100
        cmap = LinearSegmentedColormap.from_list('heatmap', colors, N=n_bins)

        # Crear figura
        fig, ax = plt.subplots(figsize=(16, 9), dpi=100)

        # Plot heatmap
        im = ax.imshow(
            heatmap_blurred,
            cmap=cmap,
            interpolation='bilinear',
            alpha=0.7,
            extent=[0, self.screen_width, self.screen_height, 0]
        )

        # Configurar ejes
        ax.set_xlim(0, self.screen_width)
        ax.set_ylim(self.screen_height, 0)
        ax.set_xlabel('X (pixels)')
        ax.set_ylabel('Y (pixels)')
        ax.set_title(title, fontsize=14, fontweight='bold')

        # Añadir colorbar
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Intensidad de interacción', rotation=270, labelpad=20)

        # Grid
        ax.grid(True, alpha=0.3, linestyle='--')

        # Guardar
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

    def generate_comparison(
        self,
        events: List[Dict[str, Any]],
        output_path: Path
    ):
        """Genera comparación lado a lado: movimientos vs clicks"""
        # Separar eventos
        move_events = [e for e in events if e.get('event_type') == 'move']
        click_events = [
            e for e in events
            if e.get('event_type') == 'click' and e.get('pressed') is True
        ]

        if not move_events and not click_events:
            print("⚠️  No hay eventos para generar comparación")
            return

        # Crear figura con 2 subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 9), dpi=100)

        # Heatmap de movimientos
        if move_events:
            heatmap_move = self._create_heatmap_array(
                [(e['x'], e['y']) for e in move_events],
                blur_radius=15
            )
            colors = ['#000033', '#0000FF', '#00FFFF', '#FFFFFF']
            cmap_move = LinearSegmentedColormap.from_list('move', colors, N=100)

            im1 = ax1.imshow(
                heatmap_move,
                cmap=cmap_move,
                interpolation='bilinear',
                alpha=0.7,
                extent=[0, self.screen_width, self.screen_height, 0]
            )
            ax1.set_title(f'Movimientos del Mouse ({len(move_events)} eventos)',
                         fontsize=12, fontweight='bold')
            plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)

        # Heatmap de clicks
        if click_events:
            heatmap_click = self._create_heatmap_array(
                [(e['x'], e['y']) for e in click_events],
                blur_radius=30
            )
            colors = ['#330000', '#FF0000', '#FFFF00', '#FFFFFF']
            cmap_click = LinearSegmentedColormap.from_list('click', colors, N=100)

            im2 = ax2.imshow(
                heatmap_click,
                cmap=cmap_click,
                interpolation='bilinear',
                alpha=0.7,
                extent=[0, self.screen_width, self.screen_height, 0]
            )
            ax2.set_title(f'Clicks del Mouse ({len(click_events)} eventos)',
                         fontsize=12, fontweight='bold')
            plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)

        # Configurar ambos ejes
        for ax in [ax1, ax2]:
            ax.set_xlim(0, self.screen_width)
            ax.set_ylim(self.screen_height, 0)
            ax.set_xlabel('X (pixels)')
            ax.set_ylabel('Y (pixels)')
            ax.grid(True, alpha=0.3, linestyle='--')

        # Guardar
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"✓ Comparación generada: {output_path}")

    def _create_heatmap_array(
        self,
        coordinates: List[Tuple[int, int]],
        blur_radius: int
    ) -> np.ndarray:
        """Crea array 2D del heatmap"""
        heatmap = np.zeros((self.screen_height, self.screen_width))

        for x, y in coordinates:
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))
            heatmap[y, x] += 1

        heatmap_blurred = gaussian_filter(heatmap, sigma=blur_radius)

        if heatmap_blurred.max() > 0:
            heatmap_blurred = heatmap_blurred / heatmap_blurred.max()

        return heatmap_blurred
