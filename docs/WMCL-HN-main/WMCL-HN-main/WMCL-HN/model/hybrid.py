import torch.nn as nn
from contra import cl
from model.backbone import Backbone
from model.classifier_ import Classifier


class WMCL_HN(nn.Module):
    def __init__(self):
        super(WMCL_HN, self).__init__()

        self.backbone = Backbone().cuda()
        self.classifier = Classifier(backbone=self.backbone).cuda()
        self.cl = cl(backbone=self.backbone).cuda()

    def forward(self, mri, pet, csf, label, lambda_):
        # 计算对比学习损失和权重
        loss_cl= self.cl(mri=mri, pet=pet, csf=csf)

        # 计算分类器的输出和损失
        output, loss_classifier = self.classifier(mri=mri, pet=pet, csf=csf, label_=label)

        # 总损失计算
        loss_hybrid = lambda_ * loss_cl + (1 - lambda_) * loss_classifier

        return loss_hybrid, output, loss_classifier
