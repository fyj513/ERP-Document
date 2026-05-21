import torch
from torch import nn, einsum
import torch.nn.functional as F


class Weight(nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = nn.Parameter(torch.randn(3).fill_(0))
        self.softmax = nn.Softmax(dim=-1)

    def forward(self):
        return self.softmax(self.weight)


class cl(nn.Module):
    def __init__(self, backbone):
        super().__init__()
        self.backbone = backbone
        self.weight = Weight()
        self.para = 0.1
        self.linear_projection_mri = nn.Linear(in_features=40, out_features=8)
        self.linear_projection_pet = nn.Linear(in_features=40, out_features=8)
        self.linear_projection_csf = nn.Linear(in_features=40, out_features=8)

    def matrix_diag(self, t):
        device = t.device
        i, j = t.shape[-2:]
        num_diag_el = min(i, j)
        diag_el = t.diagonal(dim1=-2, dim2=-1)
        return diag_el.view(-1, num_diag_el)

    def log(self, t, eps=1e-20):
        return torch.log(t + eps)

    def l2norm(self, t):
        return F.normalize(t, dim=-1, p=2)

    def compute_cl_loss(self, latents_a, latents_b):

        latents_a, latents_b = map(self.l2norm, (latents_a, latents_b))

        latents_to_b = einsum('md, nd -> mn', latents_a, latents_b) / self.para
        latents_to_a = einsum('md, nd -> mn', latents_b, latents_a) / self.para

        latents_to_b_exp, latents_to_a_exp = map(torch.exp, (latents_to_b, latents_to_a))
        latents_to_b_pos, latents_to_a_pos = map(self.matrix_diag, (latents_to_b_exp, latents_to_a_exp))
        latents_to_b_denom, latents_to_a_denom = map(lambda t: t.sum(dim=-1), (latents_to_b_exp, latents_to_a_exp))

        latents_to_b_loss = -self.log(latents_to_b_pos / latents_to_b_denom).mean(dim=-1)
        latents_to_a_loss = -self.log(latents_to_a_pos / latents_to_a_denom).mean(dim=-1)

        return (latents_to_b_loss + latents_to_a_loss) / 2

    def forward(self, mri, pet, csf):
        # 通过 backbone 获得 MRI, PET, CSF 的 latent 表示
        mri_latents, pet_latents, csf_latents = self.backbone(mri, pet, csf)

        # 线性投影
        mri_latents = self.linear_projection_mri(mri_latents)
        pet_latents = self.linear_projection_pet(pet_latents)
        csf_latents = self.linear_projection_csf(csf_latents)

        # 获取权重
        weight_pet_mri, weight_mri_csf, weight_pet_csf = self.weight()

        # 计算 MRI & CSF 损失
        cl_loss_csf_mri = self.compute_cl_loss(mri_latents, csf_latents)

        # 计算 PET & CSF 损失
        cl_loss_pet_csf = self.compute_cl_loss(pet_latents, csf_latents)

        # 计算 MRI & PET 损失
        cl_loss_pet_mri = self.compute_cl_loss(mri_latents, pet_latents)

        # 综合损失
        cl_loss = weight_mri_csf * cl_loss_csf_mri + weight_pet_csf * cl_loss_pet_csf + weight_pet_mri * cl_loss_pet_mri

        return cl_loss


