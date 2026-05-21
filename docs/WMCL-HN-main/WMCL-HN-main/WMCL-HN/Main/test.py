import torch
import numpy as np
from Other.metrics import compute_metrics

def test(test_loader=None, model=None):
    label_all = []
    all_avg_probs = []

    with torch.no_grad():
        for data in test_loader:
            mri_, pet_, csf_, label_ = data
            label_all.extend(label_.cpu().numpy())
            sum_of_probs = None

            # Accumulate probabilities from each model
            for md in model:
                _, outputs, _, = md(mri=mri_, pet=pet_, csf=csf_, label=label_, lambda_=0)
                probs = torch.softmax(outputs, dim=1)

                if sum_of_probs is None:
                    sum_of_probs = probs
                else:
                    sum_of_probs += probs

            # Calculate average probabilities
            avg_probs = sum_of_probs / len(model)
            all_avg_probs.append(avg_probs.cpu().numpy())

    # Convert list of probabilities to a single numpy array
    all_avg_probs = np.vstack(all_avg_probs)

    # Compute metrics
    test_acc, sen, spec, f1, auc = compute_metrics(
        y_true=np.array(label_all),
        y_pro=all_avg_probs
    )

    # Print the computed metrics
    print(f'test: ACC: {test_acc:.2f}%, Sen: {sen:.2f}%, Spec: {spec:.2f}%, F1: {f1:.2f}%, Auc: {auc:.2f}%')

    # Prepare the result dictionary
    result = {
        "label": label_all,
        "pro": all_avg_probs[:, 1],
        "acc": test_acc,
        "sen": sen,
        "spec": spec,
        "f1": f1,
        "auc": auc
    }

    return result
