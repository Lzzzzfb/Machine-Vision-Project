from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from angle_measurement.models import MeasurementResult
from angle_measurement.stability import StabilitySnapshot


class MeasurementSummary(QWidget):
    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        group = QGroupBox("测量结果")
        form = QFormLayout(group)
        self.angle = QLabel("--")
        self.angle.setStyleSheet("font-size: 23px; font-weight: 750; color: #2458d3")
        self.projected = QLabel("--")
        self.median = QLabel("--")
        self.stddev = QLabel("--")
        self.stability = QLabel("样本不足")
        self.confidence = QLabel("--")
        self.parallelism = QLabel("--")
        self.focus = QLabel("等待测量")
        self.focus.setWordWrap(True)
        self.status = QLabel("等待测量")
        self.status.setWordWrap(True)
        for label, control in (
            ("补偿夹角", self.angle),
            ("投影诊断角", self.projected),
            ("10 次中位数", self.median),
            ("标准差", self.stddev),
            ("稳定状态", self.stability),
            ("置信度", self.confidence),
            ("双边平行度", self.parallelism),
            ("清晰度", self.focus),
            ("状态", self.status),
        ):
            form.addRow(label, control)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)

    def set_result(self, result: MeasurementResult) -> None:
        self.angle.setText("--" if result.angle_deg is None else f"{result.angle_deg:.4f}°")
        self.projected.setText(
            "--" if result.projected_angle_deg is None else f"{result.projected_angle_deg:.4f}°"
        )
        self.confidence.setText(f"{result.confidence:.3f}")
        self.parallelism.setText(
            "--"
            if result.platform_parallelism_deg is None
            else f"{result.platform_parallelism_deg:.4f}°"
        )
        diagnostics = result.diagnostics
        focus_parts = []
        for label, key in (
            ("狭缝", "slit_focus"),
            ("边1", "platform_left_focus"),
            ("边2", "platform_right_focus"),
        ):
            value = diagnostics.get(key)
            if isinstance(value, dict):
                focus_parts.append(f"{label}:{value.get('status', '--')}")
        self.focus.setText("　".join(focus_parts) if focus_parts else "--")
        if result.valid:
            self.status.setText("有效 · 双平面补偿" if result.height_compensated else "有效 · 投影调试")
            self.status.setStyleSheet("color: #238636")
        else:
            self.status.setText("无效 · " + "；".join(result.failure_reasons))
            self.status.setStyleSheet("color: #d1242f")

    def set_stability(self, snapshot: StabilitySnapshot) -> None:
        self.median.setText(
            "--" if snapshot.median_deg is None else f"{snapshot.median_deg:.4f}°"
        )
        self.stddev.setText(
            "--" if snapshot.stddev_deg is None else f"{snapshot.stddev_deg:.4f}°"
        )
        self.stability.setText(
            f"{snapshot.status} ({snapshot.valid_count}/{snapshot.window_size})"
        )
        color = "#238636" if snapshot.stable else "#b26a00"
        self.stability.setStyleSheet(f"color: {color}; font-weight: 650")
