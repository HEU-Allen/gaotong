"""知识蒸馏演示：YOLOv10-S (教师) → YOLOv10-N (学生)"""

import torch
import torch.nn.functional as F
from ultralytics import YOLO

# ========== 1. 加载模型 ==========
print("📥 加载教师模型 YOLOv10-S (22.2M 参数)...")
teacher = YOLO('yolov10s.pt')  # 会自动下载，约 20MB

print("📥 加载学生模型 YOLOv10-N (2.3M 参数)...")
student = YOLO('yolov10n.pt')  # 你本地已有

teacher.model.eval()
student.model.eval()

# ========== 2. 蒸馏超参数 ==========
alpha = 0.5      # 硬损失权重
T = 4.0          # 温度：软化概率分布，让学生学到更多细节

# ========== 3. 准备假输入 ==========
dummy = torch.randn(1, 3, 640, 640)

# ========== 4. 前向传播 ==========
with torch.no_grad():
    t_out = teacher.model(dummy)  # 教师原始输出（未经过 NMS）
    s_out = student.model(dummy)  # 学生原始输出

# 取第一个尺度的特征做蒸馏（YOLO 是多尺度输出，简化演示）
t_logits = t_out[0]
s_logits = s_out[0]

# ========== 5. 计算蒸馏损失 ==========
# 公式：L = α * L_task + (1-α) * T² * KL(σ(z_s/T) || σ(z_t/T))

# 5.1 软损失：KL 散度（带温度 T）
t_soft = F.softmax(t_logits / T, dim=1)
s_log_soft = F.log_softmax(s_logits / T, dim=1)

kl_loss = F.kl_div(s_log_soft, t_soft, reduction='batchmean') * (T * T)

# 5.2 硬损失：学生 vs 教师（实际训练应该用真实标签 GT）
hard_loss = F.mse_loss(s_logits, t_logits)

# 5.3 总损失
total_loss = alpha * hard_loss + (1 - alpha) * kl_loss

# ========== 6. 输出结果 ==========
print("\n" + "="*50)
print("📊 知识蒸馏损失计算结果")
print("="*50)
print(f"   教师模型 : YOLOv10-S (22.2M 参数)")
print(f"   学生模型 : YOLOv10-N (2.3M 参数)")
print(f"   温度 T   : {T}")
print(f"   α 权重   : {alpha}")
print(f"   硬损失   : {hard_loss.item():.4f}")
print(f"   软损失   : {kl_loss.item():.4f}")
print(f"   总损失   : {total_loss.item():.4f}")
print("="*50)
print("\n💡 说明：")
print("   1. 软损失让小学生（N）模仿大学生（S）的推理行为")
print("   2. 温度 T 越高，教师的概率分布越'软'，信息越丰富")
print("   3. 实际训练时，硬损失应使用真实标注（Ground Truth）")
