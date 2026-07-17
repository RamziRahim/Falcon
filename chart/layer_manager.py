"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : layer_manager.py
Package : chart

Purpose
-------
Manage Falcon chart layers.

Responsibilities
----------------
• Register chart layers
• Enable / Disable layers
• Load chart presets
• Return enabled layers in render order

This module contains no rendering logic.
===============================================================================
"""

from __future__ import annotations

from copy import deepcopy

from chart.chart_models import (
    ChartLayer,
    LayerType,
    DEFAULT_LAYERS,
)


class LayerManager:
    """
    Manages all chart layers.

    The renderer requests enabled layers from this class.
    """

    def __init__(self) -> None:

        self._layers = {
            layer.layer: deepcopy(layer)
            for layer in DEFAULT_LAYERS
        }
        
        # Internal registry mapping LayerType keys to corresponding operational
        # concrete rendering class instances.
        self._registry: dict = {}

    # -------------------------------------------------------------------------
    # Layer Registration
    # -------------------------------------------------------------------------

    def register_renderer(self, layer_type: LayerType, renderer_instance: any) -> None:
        """
        Register a concrete layer renderer instance.
        """
        self._registry[layer_type] = renderer_instance

    # -------------------------------------------------------------------------
    # Layer Access
    # -------------------------------------------------------------------------

    def all_layers(self) -> list[ChartLayer]:
        """
        Return every registered layer.
        """

        return sorted(
            self._layers.values(),
            key=lambda layer: layer.order,
        )

    def enabled_layers(self) -> list[ChartLayer]:
        """
        Return enabled layers sorted by render order.
        """

        return [
            layer
            for layer in self.all_layers()
            if layer.enabled
        ]

    def get(self, layer: LayerType) -> ChartLayer | None:
        """
        Get a layer.
        """

        return self._layers.get(layer)

    # -------------------------------------------------------------------------
    # Layer State
    # -------------------------------------------------------------------------

    def enable(self, layer: LayerType) -> None:

        if layer in self._layers:
            self._layers[layer].enabled = True

    def disable(self, layer: LayerType) -> None:

        if layer in self._layers:
            self._layers[layer].enabled = False

    def toggle(self, layer: LayerType) -> None:

        if layer in self._layers:
            current = self._layers[layer]
            current.enabled = not current.enabled

    def is_enabled(self, layer: LayerType) -> bool:

        obj = self._layers.get(layer)

        if obj is None:
            return False

        return obj.enabled

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def enable_all(self) -> None:

        for layer in self._layers.values():
            layer.enabled = True

    def disable_all(self) -> None:

        for layer in self._layers.values():
            layer.enabled = False

    def reset(self) -> None:
        """
        Restore Falcon default configuration.
        """

        self._layers = {
            layer.layer: deepcopy(layer)
            for layer in DEFAULT_LAYERS
        }

    # -------------------------------------------------------------------------
    # Presets
    # -------------------------------------------------------------------------

    def load_preset(
        self,
        preset: str,
    ) -> None:
        """
        Load predefined Falcon chart presets.
        """

        self.disable_all()

        preset = preset.lower()

        if preset == "default":

            self.enable(LayerType.CANDLESTICK)
            self.enable(LayerType.VOLUME)
            self.enable(LayerType.MA20)
            self.enable(LayerType.MA50)

        elif preset == "minervini":

            self.enable(LayerType.CANDLESTICK)
            self.enable(LayerType.VOLUME)

            self.enable(LayerType.MA50)
            self.enable(LayerType.MA150)
            self.enable(LayerType.MA200)

        elif preset == "vcp":

            self.enable(LayerType.CANDLESTICK)
            self.enable(LayerType.VOLUME)

            self.enable(LayerType.MA20)
            self.enable(LayerType.MA50)

            self.enable(LayerType.VCP)

        elif preset == "breakout":

            self.enable(LayerType.CANDLESTICK)

            self.enable(LayerType.VOLUME)

            self.enable(LayerType.MA20)

            self.enable(LayerType.MA50)

            self.enable(LayerType.BREAKOUT)

            self.enable(LayerType.SUPPORT)

            self.enable(LayerType.RESISTANCE)

        elif preset == "analysis":

            for layer in self._layers.values():
                layer.enabled = True

        else:

            self.reset()

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def export_state(self) -> dict:
        """
        Export layer visibility state.

        Used to save user preferences.
        """

        return {
            layer.layer.value: layer.enabled
            for layer in self.all_layers()
        }

    def import_state(
        self,
        state: dict,
    ) -> None:
        """
        Restore user preferences.
        """

        for layer in self._layers.values():

            if layer.layer.value in state:

                layer.enabled = state[layer.layer.value]

    # -------------------------------------------------------------------------
    # Renderer Integration Hooks
    # -------------------------------------------------------------------------

    def get_enabled_renderers(self) -> list[any]:
        """
        Return enabled renderer instances in render order.
        """
        renderers = []

        for layer in self.enabled_layers():

            renderer = self._registry.get(layer.layer)

            if renderer is not None:
                renderers.append(renderer)

        return renderers