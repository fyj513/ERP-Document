import scipy.io as scio
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, recall_score, roc_auc_score, f1_score

# ===================== 1. 加载 AD vs CN 数据 =====================
print("🔹 正在加载 adni_ad_cn.mat ...")

data = scio.loadmat("adni_ad_cn.mat")

# 加载 CN（注意：这里是mync，不是mycn）
cn_mri = data["mync"][0,0]
cn_pet = data["mync"][1,0]
cn_csf = data["mync"][2,0]
cn_gnd = data["mync"][3,0].ravel()

# 加载 AD
ad_mri = data["myad"][0,0]
ad_pet = data["myad"][1,0]
ad_csf = data["myad"][2,0]
ad_gnd = data["myad"][3,0].ravel()

# 拼接数据
X_mri = np.vstack([cn_mri, ad_mri])
X_pet = np.vstack([cn_pet, ad_pet])
X_csf = np.vstack([cn_csf, ad_csf])
X = np.hstack([X_mri, X_pet, X_csf])
y = np.hstack([cn_gnd, ad_gnd])

print(f"✅ 数据加载完成！总样本：{len(y)}")
print(f"   CN：{len(cn_gnd)}")
print(f"   AD：{len(ad_gnd)}")
print(f"   特征维度：{X.shape[1]}")

# 标准化
scaler = StandardScaler()
X = scaler.fit_transform(X)

# ===================== 2. 5 折交叉验证 =====================
kf = KFold(n_splits=5, shuffle=True, random_state=42)

# 模型
models = {
    "LR": LogisticRegression(max_iter=1000),
    "SVM": SVC(kernel="linear", probability=True),
    "XGBoost": GradientBoostingClassifier()
}

results = []

print("\n" + "="*60)
print("📌 传统基线模型运行：AD vs CN")
print("="*60)

for name, clf in models.items():
    acc_list = []
    sen_list = []
    spec_list = []
    f1_list = []
    auc_list = []

    for train_idx, test_idx in kf.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)
        y_prob = clf.predict_proba(X_test)[:, 1]

        acc = accuracy_score(y_test, y_pred)
        sen = recall_score(y_test, y_pred, pos_label=1)
        spec = recall_score(y_test, y_pred, pos_label=0)
        f1 = f1_score(y_test, y_pred)
        auc = roc_auc_score(y_test, y_prob)

        acc_list.append(acc)
        sen_list.append(sen)
        spec_list.append(spec)
        f1_list.append(f1)
        auc_list.append(auc)

    acc = np.mean(acc_list)
    sen = np.mean(sen_list)
    spec = np.mean(spec_list)
    f1 = np.mean(f1_list)
    auc = np.mean(auc_list)

    results.append([name, acc, sen, spec, f1, auc])

    print(f"\n【{name}】")
    print(f"ACC  {acc:.2%}")
    print(f"SEN  {sen:.2%}")
    print(f"SPEC {spec:.2%}")
    print(f"F1   {f1:.2%}")
    print(f"AUC  {auc:.2%}")

# ===================== 3. 保存 Excel =====================
df = pd.DataFrame(results, columns=["Model", "ACC", "SEN", "SPEC", "F1", "AUC"])
df.to_excel("baseline_ad_cn_result.xlsx", index=False)

print("\n" + "="*60)
print("🎉 AD vs CN 基线全部完成！")
print("✅ 结果已保存：baseline_ad_cn_result.xlsx")