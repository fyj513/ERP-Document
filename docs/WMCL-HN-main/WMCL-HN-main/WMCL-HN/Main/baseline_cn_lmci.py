import scipy.io as scio
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, recall_score, roc_auc_score, f1_score

# ===================== 1. 加载 CN vs LMCI 数据 =====================
print("🔹 正在加载 adni_cn_lmci.mat ...")

data = scio.loadmat("adni_cn_lmci.mat")

# 加载 CN
cn_mri = data["mycn"][0,0]
cn_pet = data["mycn"][1,0]
cn_csf = data["mycn"][2,0]
cn_gnd = data["mycn"][3,0].ravel()

# 加载 LMCI
lmci_mri = data["mylmci"][0,0]
lmci_pet = data["mylmci"][1,0]
lmci_csf = data["mylmci"][2,0]
lmci_gnd = data["mylmci"][3,0].ravel()

# 拼接数据
X_mri = np.vstack([cn_mri, lmci_mri])
X_pet = np.vstack([cn_pet, lmci_pet])
X_csf = np.vstack([cn_csf, lmci_csf])
X = np.hstack([X_mri, X_pet, X_csf])
y = np.hstack([cn_gnd, lmci_gnd])

print(f"✅ 数据加载完成！总样本：{len(y)}")
print(f"   CN：{len(cn_gnd)}")
print(f"   LMCI：{len(lmci_gnd)}")
print(f"   特征维度：{X.shape[1]}")

# 标准化
scaler = StandardScaler()
X = scaler.fit_transform(X)

# ===================== 2. 5 折交叉验证 =====================
kf = KFold(n_splits=5, shuffle=True, random_state=42)

# 模型定义
models = {
    "LR": LogisticRegression(max_iter=1000),
    "SVM": SVC(kernel="linear", probability=True),
    "XGBoost": GradientBoostingClassifier()
}

results = []

print("\n" + "="*60)
print("📌 传统基线模型运行：CN vs LMCI")
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

    # 平均
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
df.to_excel("baseline_cn_lmci_result.xlsx", index=False)

print("\n" + "="*60)
print("🎉 全部完成！")
print("✅ 结果已保存：baseline_cn_lmci_result.xlsx")