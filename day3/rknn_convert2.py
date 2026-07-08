from rknn.api import RKNN

print("🔄 重新转换 ONNX → RKNN（rk3566 平台）...")

rknn = RKNN()

rknn.config(
    mean_values=[[0, 0, 0]],
    std_values=[[255, 255, 255]],
    target_platform='rk3566',  # 改为模拟器支持的平台
    optimization_level=3
)

rknn.load_onnx(model='yolov10n.onnx')
rknn.build(do_quantization=True, dataset='calib.txt')
rknn.export_rknn('yolov10n_rk3566.rknn')
print("✅ RKNN 导出完成：yolov10n_rk3566.rknn")

rknn.release()
