import numpy as np
import warnings
import sys
import os

# 屏蔽无关警告
warnings.filterwarnings("ignore")
# 让Python能找到Other文件夹
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入原代码的工具
from Other.load_data import data_load
from Other.metrics import compute_metrics  # 你的评估函数

# -------------------------- 全局配置 --------------------------
RANDOM_SEED = 42
N_SPLITS = 5  # 和论文一致的五折交叉验证
DATA_PATH = 'adni_data.mat'

# -------------------------- 1. 加载并合并AD和NC的数据 --------------------------
def load_ad_nc_data():
    """加载NC和AD的数据，合并成完整的二分类数据集"""
    # 用原代码的函数分别加载NC和AD的数据
    print("正在加载NC（健康人）数据...")
    mri_nc, pet_nc, csf_nc, gnd_nc = data_load(DATA_PATH, 'mync')
    print(f"NC数据：{len(mri_nc)}个样本")

    print("正在加载AD（患者）数据...")
    mri_ad, pet_ad, csf_ad, gnd_ad = data_load(DATA_PATH, 'myad')
    print(f"AD数据：{len(mri_ad)}个样本")

    # 合并所有模态的数据和标签
    mri_all = np.concatenate([mri_nc, mri_ad], axis=0)
    pet_all = np.concatenate([pet_nc, pet_ad], axis=0)
    csf_all = np.concatenate([csf_nc, csf_ad], axis=0)
    # 标签：NC是0，AD是1（原数据里gnd_nc全是0，gnd_ad全是1，正好直接用）
    labels_all = np.concatenate([gnd_nc, gnd_ad], axis=0)

    # 拼接全量特征（给基础SVM、Lasso-SVM用）
    all_features = np.concatenate([mri_all, pet_all, csf_all], axis=1)

    print("\n✅ 数据合并完成！")
    print(f"总样本数：{len(labels_all)}")
    print(f"MRI形状: {mri_all.shape}")
    print(f"全量特征形状: {all_features.shape}")
    print(f"标签分布：0(NC)={np.sum(labels_all==0)}个，1(AD)={np.sum(labels_all==1)}个")

    return {
        "mri": mri_all,
        "pet": pet_all,
        "csf": csf_all,
        "all_features": all_features,
        "labels": labels_all
    }

# -------------------------- 2. 4个SVM基线的核心实现 --------------------------
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, GridSearchCV
from sklearn.linear_model import Lasso
from sklearn.feature_selection import SelectFromModel
from sklearn.metrics.pairwise import linear_kernel

def run_single_baseline(full_data, baseline_name):
    """跑单个SVM基线的五折实验"""
    X_all = full_data["all_features"]
    X_mri = full_data["mri"]
    X_pet = full_data["pet"]
    X_csf = full_data["csf"]
    y = full_data["labels"]

    # 分层五折交叉验证，保证每折的正负样本比例一致
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_SEED)
    fold_results = []

    print(f"\n{'='*50}")
    print(f"开始运行基线：{baseline_name}")
    print(f"{'='*50}")

    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X_all, y)):
        print(f"\n--- 第 {fold_idx+1} 折 ---")
        # 划分训练集和测试集
        X_train_all, X_test_all = X_all[train_idx], X_all[test_idx]
        mri_train, mri_test = X_mri[train_idx], X_mri[test_idx]
        pet_train, pet_test = X_pet[train_idx], X_pet[test_idx]
        csf_train, csf_test = X_csf[train_idx], X_csf[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # ========== 1. 基础SVM ==========
        if baseline_name == "BaseSVM":
            # 标准化：只在训练集拟合，防止数据泄露
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train_all)
            X_test_scaled = scaler.transform(X_test_all)

            # 网格搜索调优超参数
            param_grid = {
                'C': [0.001, 0.01, 0.1, 1, 10, 100],
                'kernel': ['linear']
            }
            grid_search = GridSearchCV(
                SVC(probability=True, random_state=RANDOM_SEED, class_weight='balanced'),
                param_grid, cv=5, scoring='accuracy', n_jobs=1
            )
            grid_search.fit(X_train_scaled, y_train)
            best_model = grid_search.best_estimator_
            print(f"最优参数：{grid_search.best_params_}")

            # 预测
            y_pred = best_model.predict(X_test_scaled)
            y_prob = best_model.predict_proba(X_test_scaled)

        # ========== 2. Lasso-SVM ==========
        elif baseline_name == "LassoSVM":
            # 先标准化
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train_all)
            X_test_scaled = scaler.transform(X_test_all)

            # Lasso特征筛选
            lasso = Lasso(alpha=0.01, max_iter=10000, random_state=RANDOM_SEED)
            selector = SelectFromModel(lasso)
            X_train_selected = selector.fit_transform(X_train_scaled, y_train)
            X_test_selected = selector.transform(X_test_scaled)
            print(f"特征筛选：{X_train_scaled.shape[1]}维 → {X_train_selected.shape[1]}维")

            # 兜底：如果筛选后没特征，用原始特征
            if X_train_selected.shape[1] == 0:
                print("警告：Lasso筛选后无特征，改用原始特征")
                X_train_selected, X_test_selected = X_train_scaled, X_test_scaled

            # 网格搜索调参
            param_grid = {'C': [0.001, 0.01, 0.1, 1, 10, 100], 'kernel': ['linear']}
            grid_search = GridSearchCV(
                SVC(probability=True, random_state=RANDOM_SEED, class_weight='balanced'),
                param_grid, cv=5, scoring='accuracy', n_jobs=1
            )
            grid_search.fit(X_train_selected, y_train)
            best_model = grid_search.best_estimator_
            print(f"最优参数：{grid_search.best_params_}")

            # 预测
            y_pred = best_model.predict(X_test_selected)
            y_prob = best_model.predict_proba(X_test_selected)

        # ========== 3. MKSVM（多核SVM） ==========
        elif baseline_name == "MKSVM":
            # 每个模态单独标准化（适配不同模态的分布）
            scaler_mri = StandardScaler()
            scaler_pet = StandardScaler()
            scaler_csf = StandardScaler()

            mri_train_scaled = scaler_mri.fit_transform(mri_train)
            pet_train_scaled = scaler_pet.fit_transform(pet_train)
            csf_train_scaled = scaler_csf.fit_transform(csf_train)

            mri_test_scaled = scaler_mri.transform(mri_test)
            pet_test_scaled = scaler_pet.transform(pet_test)
            csf_test_scaled = scaler_csf.transform(csf_test)

            # 计算每个模态的线性核矩阵
            # 训练集核矩阵
            K_mri_train = linear_kernel(mri_train_scaled, mri_train_scaled)
            K_pet_train = linear_kernel(pet_train_scaled, pet_train_scaled)
            K_csf_train = linear_kernel(csf_train_scaled, csf_train_scaled)
            K_train = (K_mri_train + K_pet_train + K_csf_train) / 3  # 等权重融合

            # 测试集核矩阵（必须和训练集计算，不能自己和自己算）
            K_mri_test = linear_kernel(mri_test_scaled, mri_train_scaled)
            K_pet_test = linear_kernel(pet_test_scaled, pet_train_scaled)
            K_csf_test = linear_kernel(csf_test_scaled, csf_train_scaled)
            K_test = (K_mri_test + K_pet_test + K_csf_test) / 3

            # 网格搜索调参（注意kernel='precomputed'，用我们提前算好的核矩阵）
            param_grid = {'C': [0.001, 0.01, 0.1, 1, 10, 100]}
            grid_search = GridSearchCV(
                SVC(kernel='precomputed', probability=True, random_state=RANDOM_SEED, class_weight='balanced'),
                param_grid, cv=5, scoring='accuracy', n_jobs=1
            )
            grid_search.fit(K_train, y_train)
            best_model = grid_search.best_estimator_
            print(f"最优参数：{grid_search.best_params_}")

            # 预测
            y_pred = best_model.predict(K_test)
            y_prob = best_model.predict_proba(K_test)

        # ========== 4. Lasso-MKSVM ==========
        elif baseline_name == "LassoMKSVM":
            # 每个模态单独标准化
            scaler_mri = StandardScaler()
            scaler_pet = StandardScaler()
            scaler_csf = StandardScaler()

            mri_train_scaled = scaler_mri.fit_transform(mri_train)
            pet_train_scaled = scaler_pet.fit_transform(pet_train)
            csf_train_scaled = scaler_csf.fit_transform(csf_train)

            mri_test_scaled = scaler_mri.transform(mri_test)
            pet_test_scaled = scaler_pet.transform(pet_test)
            csf_test_scaled = scaler_csf.transform(csf_test)

            # 给每个模态单独做Lasso特征筛选
            def lasso_select(train_feat, test_feat, y_tr):
                lasso = Lasso(alpha=0.01, max_iter=10000, random_state=RANDOM_SEED)
                selector = SelectFromModel(lasso)
                train_sel = selector.fit_transform(train_feat, y_tr)
                test_sel = selector.transform(test_feat)
                # 兜底：如果筛选后没特征，用原始特征
                if train_sel.shape[1] == 0:
                    return train_feat, test_feat
                return train_sel, test_sel

            # 对三个模态分别筛选
            mri_train_sel, mri_test_sel = lasso_select(mri_train_scaled, mri_test_scaled, y_train)
            pet_train_sel, pet_test_sel = lasso_select(pet_train_scaled, pet_test_scaled, y_train)
            csf_train_sel, csf_test_sel = lasso_select(csf_train_scaled, csf_test_scaled, y_train)
            print(f"MRI筛选后：{mri_train_scaled.shape[1]}维 → {mri_train_sel.shape[1]}维")
            print(f"PET筛选后：{pet_train_scaled.shape[1]}维 → {pet_train_sel.shape[1]}维")
            print(f"CSF筛选后：{csf_train_scaled.shape[1]}维 → {csf_train_sel.shape[1]}维")

            # 计算筛选后的核矩阵
            K_mri_train = linear_kernel(mri_train_sel, mri_train_sel)
            K_pet_train = linear_kernel(pet_train_sel, pet_train_sel)
            K_csf_train = linear_kernel(csf_train_sel, csf_train_sel)
            K_train = (K_mri_train + K_pet_train + K_csf_train) / 3

            K_mri_test = linear_kernel(mri_test_sel, mri_train_sel)
            K_pet_test = linear_kernel(pet_test_sel, pet_train_sel)
            K_csf_test = linear_kernel(csf_test_sel, csf_train_sel)
            K_test = (K_mri_test + K_pet_test + K_csf_test) / 3

            # 网格搜索调参
            param_grid = {'C': [0.001, 0.01, 0.1, 1, 10, 100]}
            grid_search = GridSearchCV(
                SVC(kernel='precomputed', probability=True, random_state=RANDOM_SEED, class_weight='balanced'),
                param_grid, cv=5, scoring='accuracy', n_jobs=1
            )
            grid_search.fit(K_train, y_train)
            best_model = grid_search.best_estimator_
            print(f"最优参数：{grid_search.best_params_}")

            # 预测
            y_pred = best_model.predict(K_test)
            y_prob = best_model.predict_proba(K_test)

        else:
            raise ValueError("基线名错误！可选：BaseSVM / LassoSVM / MKSVM / LassoMKSVM")

        # 计算评估指标（用你原代码的metrics函数，保证评估标准100%一致）
        acc, sen, spe, f1, auc = compute_metrics(y_test, y_prob)
        metrics = {
            "ACC": acc,
            "SEN": sen,
            "SPE": spe,
            "F1": f1,
            "AUC": auc
        }
        fold_results.append(metrics)
        print(f"当前折指标：{metrics}")

    # 计算五折的平均结果
    print(f"\n===== {baseline_name} 五折平均结果 =====")
    avg_metrics = {}
    for key in fold_results[0].keys():
        avg_metrics[key] = np.mean([m[key] for m in fold_results])
        print(f"{key}: {avg_metrics[key]:.4f}")

    return {
        "每折结果": fold_results,
        "平均结果": avg_metrics
    }

# -------------------------- 3. 主函数：跑所有4个基线 --------------------------
if __name__ == "__main__":
    # 1. 加载合并好的数据
    full_data = load_ad_nc_data()

    # 2. 定义要跑的4个基线
    baselines = ["BaseSVM", "LassoSVM", "MKSVM", "LassoMKSVM"]

    # 3. 循环跑所有基线
    all_results = {}
    for baseline in baselines:
        res = run_single_baseline(full_data, baseline)
        all_results[baseline] = res

    # 4. 保存所有结果
    np.save("svm_ad_vs_nc_results.npy", all_results, allow_pickle=True)
    print(f"\n{'='*60}")
    print("✅ 所有4个SVM基线实验完成！结果已保存到 svm_ad_vs_nc_results.npy")
    print(f"{'='*60}")

    # 5. 打印最终汇总结果，方便你直接复制到论文里
    print("\n📊 最终汇总结果（AD vs NC 五折平均）：")
    print("-"*80)
    for baseline in baselines:
        avg = all_results[baseline]["平均结果"]
        print(f"{baseline}: ACC={avg['ACC']:.2f}%, SEN={avg['SEN']:.2f}%, SPE={avg['SPE']:.2f}%, F1={avg['F1']:.2f}%, AUC={avg['AUC']:.2f}%")
    print("-"*80)