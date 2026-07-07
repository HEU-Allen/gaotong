from ultralytics import YOLO
model = YOLO('yolov10n.pt')
model.export(format='onnx', imgsz=640, simplify=True, opset=17)
print('✅ 导出完成: yolov10n.onnx')
