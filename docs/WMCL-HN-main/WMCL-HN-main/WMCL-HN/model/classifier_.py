import torch
import torch.nn as nn

# 简单的多层感知机（MLP）模型
class MLP(nn.Module):
    def __init__(self, input_size):
        super(MLP, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 32),
            nn.ReLU(),
            nn.Linear(32, 2)  # 输出层：2个类别
        )

    def forward(self, x):
        return self.network(x)

# 分类器，包含一个MLP网络和一个backbone
class Classifier(nn.Module):
    def __init__(self, *, backbone):
        super(Classifier, self).__init__()
        self.mlp = MLP(input_size=120)
        self.backbone = backbone
        self.criterion = nn.CrossEntropyLoss()

    def forward(self, mri, pet, csf, label_):
        # 从backbone提取特征
        mri_latents, pet_latents, csf_latents = self.backbone(mri=mri, pet=pet, csf=csf)
        # 拼接特征
        fuse_feat = torch.cat((mri_latents, pet_latents, csf_latents), dim=1)
        # 通过MLP进行分类
        output = self.mlp(fuse_feat)
        # 计算交叉熵损失
        ce_loss = self.criterion(output, label_)
        return output, ce_loss