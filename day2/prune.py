"""模型剪枝演示：YOLOv10-N L1 非结构化剪枝 + 通道剪枝分析"""

import torch
import torch.nn.utils.prune as prune
from ultralytics import YOLO

# ========== 1. 加载模型 ==========
model = YOLO('yolov10n.pt')
net = model.model

def count_params(m):
    """统计总参数量（原始）"""
    return sum(p.numel() for p in m.parameters())

original = count_params(net)
print(f"📦 原始参数量: {original:,} ({original/1e6:.2f}M)")

# ========== 2. L1 非结构化剪枝（30%）==========
print("\n🔧 执行 L1 非结构化剪枝（剪掉 30% 权重连接）...")

# 收集所有 Conv2d 的 weight
conv_modules = []
for module in net.modules():
    if isinstance(module, torch.nn.Conv2d):
        conv_modules.append((module, 'weight'))

# 全局剪枝：在所有 Conv2d 的 weight 中统一剪掉 30%（更稳定）
prune.global_unstructured(conv_modules, pruning_method=prune.L1Unstructured, amount=0.3)

# 统计非零参数（关键：通过 module.weight 读取，mask 才会生效）
nonzero = 0
for module in net.modules():
    if isinstance(module, torch.nn.Conv2d):
        # module.weight 是 property，会应用 mask
        nonzero += torch.count_nonzero(module.weight).item()

print(f"   剪枝后非零参数: {nonzero:,} ({nonzero/1e6:.2f}M)")
print(f"   稀疏度（零参数占比）: {(1 - nonzero/original)*100:.1f}%")

# 直观验证：打印第一个 Conv 层的 weight，看看有没有零
for module in net.modules():
    if isinstance(module, torch.nn.Conv2d):
        zeros = (module.weight == 0).sum().item()
        total = module.weight.numel()
        print(f"   示例层 {module}: {zeros}/{total} 个零 ({zeros/total*100:.1f}%)")
        break

# ========== 3. 通道剪枝分析 ==========
print("\n📋 通道剪枝分析（基于卷积核 L1 范数）:")
for name, module in net.named_modules():
    if isinstance(module, torch.nn.Conv2d):
        weight = module.weight.data
        channel_norm = weight.abs().sum(dim=[1, 2, 3])
        n_prune = int(0.1 * len(channel_norm))
        print(f"   {name:30s}: 共 {len(channel_norm):4d} 通道，建议剪除 {n_prune:3d} 个")
        break

# ========== 4. 对比总结 ==========
print("\n" + "="*50)
print("📊 剪枝前后对比")
print("="*50)
print(f"   原始参数量    : {original:,} ({original/1e6:.2f}M)")
print(f"   非零参数量    : {nonzero:,} ({nonzero/1e6:.2f}M)")
print(f"   理论压缩率    : {original/nonzero:.2f}x")
print(f"   实际稀疏度    : {(1-nonzero/original)*100:.1f}%")
print("="*50)
print("\n💡 说明：")
print("   1. global_unstructured 在所有 Conv2d 中统一按 L1 范数排序剪枝")
print("   2. 剪枝后 module.weight 会应用 mask，原始数据仍存在")
print("   3. 实际部署需配合 fine-tuning 恢复精度，或用 structured prune 直接删通道")
