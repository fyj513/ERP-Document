import scipy.io as scio
import numpy as np

# ===================== 1. 定义要检查的mat文件列表 =====================
# 把你所有生成的mat文件名都加进来
mat_files = [
    "adni_ad_cn.mat",
    "adni_cn_emci.mat",
    "adni_cn_lmci.mat",
    "adni_ad_emci.mat",
    "adni_ad_lmci.mat"
]

# ===================== 2. 逐个检查标签 =====================
for mat_file in mat_files:
    print("\n" + "="*60)
    print(f"📌 正在检查：{mat_file}")
    print("="*60)
    
    try:
        # 加载mat文件
        data = scio.loadmat(mat_file)
        
        # 遍历所有键（排除mat自带的__header__等）
        for key in data.keys():
            if key.startswith('__'):
                continue
            
            # 提取该类别的数据
            class_data = data[key]
            # 标签在第3行第0列（和你之前生成的格式一致）
            labels = class_data[3, 0].ravel()
            
            # 统计标签
            unique_labels, counts = np.unique(labels, return_counts=True)
            
            print(f"\n【类别：{key}】")
            print(f"   总样本数：{len(labels)}")
            print(f"   标签取值：{unique_labels.tolist()}")
            print(f"   标签分布：{dict(zip(unique_labels, counts))}")
            
            # 检查MRI/PET/CSF的维度
            mri_dim = class_data[0, 0].shape
            pet_dim = class_data[1, 0].shape
            csf_dim = class_data[2, 0].shape
            print(f"   MRI维度：{mri_dim}")
            print(f"   PET维度：{pet_dim}")
            print(f"   CSF维度：{csf_dim}")
            
    except FileNotFoundError:
        print(f"❌ 错误：找不到文件 {mat_file}")
    except Exception as e:
        print(f"❌ 错误：{e}")

print("\n" + "="*60)
print("🎉 所有文件检查完成！")