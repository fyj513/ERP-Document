import scipy.io as scio

# 检查adni_ad_cn.mat的所有键
data = scio.loadmat("adni_ad_cn.mat")

print("✅ adni_ad_cn.mat 里的所有变量名：")
for key in data.keys():
    if not key.startswith('__'):  # 排除mat自带的系统变量
        print(f"   - {key}")