import torch
from torch.utils.data import Dataset

class MultiModalDataset(Dataset):
    def __init__(self, mri, pet, csf, labels):
        self.mri = mri
        self.pet = pet
        self.csf = csf
        self.labels = labels

    def __len__(self):
        return len(self.mri)

    def __getitem__(self, index):
        mri = torch.as_tensor(self.mri[index], dtype=torch.float32).cuda()
        pet = torch.as_tensor(self.pet[index], dtype=torch.float32).cuda()
        csf = torch.as_tensor(self.csf[index], dtype=torch.float32).cuda()
        labels = torch.as_tensor(self.labels[index], dtype=torch.long).cuda()

        return mri, pet, csf, labels