# 假设 contra 和 model 文件夹在同一级（项目根目录下）

import sys
import os

# 第一步：先定义 project_root
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file))

# 第二步：再使用 project_root 拼接路径
contra_path = os.path.join(project_root, "WMCL-HN", "model")

# 把路径加入搜索列表
if contra_path not in sys.path:
    sys.path.append(contra_path)
contra_path = os.path.join(project_root, "C:/Users/冯妍锦/Desktop/WMCL-HN-main/WMCL-HN-main/WMCL-HN/model")
if contra_path not in sys.path:
    sys.path.append(contra_path)

import torch
import torch.optim as optim
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from torch.utils.data import DataLoader
from model.hybrid import WMCL_HN
from Other.dataset import MultiModalDataset
from Other.load_data import data_load
from Main.train_val import train_val
from Main.test import test

# Load data
path = "C:/Users/冯妍锦/Desktop/WMCL-HN-main/WMCL-HN-main/WMCL-HN/Main/adni_ad_lmci.mat"
# 1. 加载 mat 文件里的两个类别
mri1, pet1, csf1, gnd1 = data_load(path=path, str='mylmci')
mri2, pet2, csf2, gnd2 = data_load(path=path, str='myad')
# 2. 把两个类别拼接到一起
mri, pet, csf, gnd = [np.concatenate((data1, data2), axis=0)
                      for data1, data2 in zip((mri1, pet1, csf1, gnd1), (mri2, pet2, csf2, gnd2))]
gnd=gnd.astype(np.int64)# 把标签转成整数
# Parameters
num_epochs = 250
batch_size_train = 20
batch_size_val = 20

# Lists to store results
results = []

# Main loop 外层循环：种子重复（Seed 2/4/6/8/10）
 # 目的：用5个不同的随机种子重复实验，避免单次实验的偶然性
    # 论文里会取这5个种子的平均结果，更有说服力
for seed in [2, 4, 6, 8, 10]:
 #中层循环：Fold1（划分 TrainVal + Test）
 # 目的：第1层5折，把数据分成「训练验证集（80%）」和「测试集（20%）」
    # 测试集在Fold1里完全不动，只用来最后测试
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)  # Use seed for reproducibility

    for fold1, (train_index, test_index) in enumerate(skf.split(mri, gnd)):
        print(f"Seed {seed}, Fold1 {fold1 + 1}")
        model = []

        # Split data
        x_train_val_mri, x_test_mri = mri[train_index], mri[test_index]
        x_train_val_pet, x_test_pet = pet[train_index], pet[test_index]
        x_train_val_csf, x_test_csf = csf[train_index], csf[test_index]
        y_train_val, y_test = gnd[train_index], gnd[test_index]

        test_dataset = MultiModalDataset(mri=x_test_mri, pet=x_test_pet, csf=x_test_csf, labels=y_test)
        test_loader = DataLoader(test_dataset, batch_size=len(y_test), shuffle=False)
#内层循环：Fold2（划分 Train + Val）
# 目的：第2层5折，把TrainVal再分成「训练集（64%）」和「验证集（16%）」
    # 验证集用来选最优模型（保存checkpoint.pt）
        for fold, (train_index, val_index) in enumerate(skf.split(x_train_val_mri, y_train_val)):
            print(f"Seed {seed}, Fold1 {fold1 + 1}, Fold2 {fold + 1}")

            # Split training and validation data
            x_train_mri, x_val_mri = x_train_val_mri[train_index], x_train_val_mri[val_index]
            x_train_pet, x_val_pet = x_train_val_pet[train_index], x_train_val_pet[val_index]
            x_train_csf, x_val_csf = x_train_val_csf[train_index], x_train_val_csf[val_index]
            y_train, y_val = y_train_val[train_index], y_train_val[val_index]

            # Create datasets and dataloaders
            train_dataset = MultiModalDataset(mri=x_train_mri, pet=x_train_pet, csf=x_train_csf, labels=y_train)
            val_dataset = MultiModalDataset(mri=x_val_mri, pet=x_val_pet, csf=x_val_csf, labels=y_val)
            train_loader = DataLoader(train_dataset, batch_size=batch_size_train, shuffle=True)
            val_loader = DataLoader(val_dataset, batch_size=batch_size_val, shuffle=False)


            # Initialize and train the model
            # 1. 初始化模型，放到GPU上
            HyNet = WMCL_HN().cuda()
            # 2. 定义SGD优化器
            optimizer = optim.SGD(HyNet.parameters(), lr=0.01, momentum=0.9, weight_decay=0)
           # 3. 训练250个epoch，同时在验证集上评估
            train_val(num_epochs=num_epochs, train_loader=train_loader, val_loader=val_loader, optimizer=optimizer, model=HyNet)
            # 4. 加载验证集上表现最好的模型
            HyNet.load_state_dict(torch.load('checkpoint.pt'))
            model.append(HyNet)# 把这个Fold2的最优模型存起来

        # Test model
        # 1. 用5个Fold2的模型在Test集上测试
        result = test(test_loader=test_loader, model=model)
        results.append(result)
        # 2. 把所有结果存到Excel里
        # Save results to Excel
        df = pd.DataFrame(results)
        df.to_excel("result_ad_vs_lmci.xlsx", index=False)
