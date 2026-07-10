import cv2
import time

for camera_id in [0, 1, 2]:
    print(f"\n正在测试摄像头编号：{camera_id}")

    cap = cv2.VideoCapture(camera_id, cv2.CAP_AVFOUNDATION)

    if not cap.isOpened():
        print(f"摄像头 {camera_id} 打开失败")
        continue

    time.sleep(1)

    ok = False

    for i in range(30):
        ret, frame = cap.read()

        if ret:
            print(f"✅ 摄像头 {camera_id} 读取成功")
            ok = True

            while True:
                cv2.imshow(f"Camera {camera_id}", frame)

                ret, frame = cap.read()
                if not ret:
                    break

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            break

    cap.release()
    cv2.destroyAllWindows()

    if ok:
        print(f"\n请记住：可用摄像头编号是 {camera_id}")
        break
else:
    print("\n❌ 所有摄像头编号都读取失败")
    print("请检查 Mac 摄像头权限，或者关闭正在占用摄像头的软件，比如微信、腾讯会议、Zoom、FaceTime。")