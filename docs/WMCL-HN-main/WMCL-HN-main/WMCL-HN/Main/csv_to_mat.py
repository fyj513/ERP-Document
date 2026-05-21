import pandas as pd
import numpy as np
import scipy.io as scio
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

# ===================== 1. 加载CSV文件 =====================
print("🔹 正在加载CSV文件...")

# 👇 这里换成你自己的CSV绝对路径（复制你之前的就行）
csv_path = r'C:\Users\冯妍锦\Desktop\WMCL-HN-main\WMCL-HN-main\WMCL-HN\Main\ADNI_Master_Dataset.csv'

df = pd.read_csv(
    csv_path,
    sep=None,
    engine='python',
    on_bad_lines='skip',
    encoding='gbk'
)

print(f"✅ CSV加载完成，总样本数：{len(df)}")
print(f"数据类别：{sorted(df['Group'].unique())}")

# ===================== 2. 提取特征 =====================
mri_cols = [col for col in df.columns if col.startswith('MRI_')]
pet_cols = [col for col in df.columns if col.startswith('PET_')]
csf_cols = ['CSF_ABeta', 'CSF_Tau', 'CSF_PTau']

all_mri = df[mri_cols].values
all_pet = df[pet_cols].values
all_csf = df[csf_cols].values
all_group = df['Group'].values

# 处理缺失值
imputer = SimpleImputer(strategy='mean')
all_mri = imputer.fit_transform(all_mri)
all_pet = imputer.fit_transform(all_pet)
all_csf = imputer.fit_transform(all_csf)

# 标准化
scaler_mri = StandardScaler()
scaler_pet = StandardScaler()
scaler_csf = StandardScaler()

all_mri = scaler_mri.fit_transform(all_mri)
all_pet = scaler_pet.fit_transform(all_pet)
all_csf = scaler_csf.fit_transform(all_csf)

print(f"✅ 特征处理完成")
print(f"MRI:{len(mri_cols)}维  PET:{len(pet_cols)}维  CSF:{len(csf_cols)}维")

# ===================== 3. 生成标准MAT文件 =====================
def generate_mat(output, neg_class, pos_class):
    print("\n" + "="*50)
    print(f"📌 生成 {output} ： {neg_class} vs {pos_class}")

    mask_neg = (all_group == neg_class)
    mask_pos = (all_group == pos_class)

    mri_n = all_mri[mask_neg]
    pet_n = all_pet[mask_neg]
    csf_n = all_csf[mask_neg]
    gnd_n = np.zeros((len(mri_n), 1), dtype=np.int64)

    mri_p = all_mri[mask_pos]
    pet_p = all_pet[mask_pos]
    csf_p = all_csf[mask_pos]
    gnd_p = np.ones((len(mri_p), 1), dtype=np.int64)

    # 格式 100% 匹配你的旧 adni_data.mat
    data_neg = np.empty((4, 1), dtype=object)
    data_neg[0,0] = mri_n
    data_neg[1,0] = pet_n
    data_neg[2,0] = csf_n
    data_neg[3,0] = gnd_n

    data_pos = np.empty((4, 1), dtype=object)
    data_pos[0,0] = mri_p
    data_pos[1,0] = pet_p
    data_pos[2,0] = csf_p
    data_pos[3,0] = gnd_p

    mat = {
        f"my{neg_class.lower()}": data_neg,
        f"my{pos_class.lower()}": data_pos
    }

    scio.savemat(output, mat)
    print(f"✅ {output} 生成成功！")
    print(f"   {neg_class}：{len(mri_n)} 个")
    print(f"   {pos_class}：{len(mri_p)} 个")

# ===================== 4. 开始生成你要的两个文件 =====================
# 1. CN vs EMCI
generate_mat("adni_cn_emci.mat", "CN", "EMCI")

# 2. CN vs LMCI
generate_mat("adni_cn_lmci.mat", "CN", "LMCI")

print("\n" + "="*50)
print("🎉 全部完成！")
print("生成文件：")
print("  1. adni_cn_emci.mat")
print("  2. adni_cn_lmci.mat")
print("文件都在 Main 文件夹里，可以直接跑 main.py！")