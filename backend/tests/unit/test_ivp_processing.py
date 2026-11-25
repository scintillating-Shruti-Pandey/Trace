import numpy as np

from app.ivp.processing import analyze_hog, run_full_ivp_pipeline


def test_analyze_hog_returns_complete_descriptor_without_cv2_hogdescriptor(monkeypatch):
    import cv2

    monkeypatch.delattr(cv2, "HOGDescriptor", raising=False)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:380, 80:560] = (120, 115, 110)

    result = analyze_hog(frame)

    assert result["metrics"]["descriptor_length"] == 3780
    assert result["metrics"]["descriptor_nonzero"] > 0


def test_full_ivp_pipeline_runs_with_portable_hog(monkeypatch):
    import cv2

    monkeypatch.delattr(cv2, "HOGDescriptor", raising=False)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:, 320:] = (180, 180, 180)

    result = run_full_ivp_pipeline(frame)

    assert "hog" in result
    assert result["hog"]["metrics"]["descriptor_length"] == 3780
