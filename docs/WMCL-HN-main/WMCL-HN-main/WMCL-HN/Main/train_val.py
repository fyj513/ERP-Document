import torch

def train_val(num_epochs=400, train_loader=None, val_loader=None, optimizer=None, model=None):

    best_val_loss = float('inf')

    for epoch in range(num_epochs):
        model.train()
        running_mixed_loss = 0.0
        correct_train = 0
        #训练刚开始（epoch=0）：lambda_ = 1，100% 用对比学习损失（L_cl）训练，让模型先学好多模态特征对齐
        #训练结束（epoch=249）：lambda_ = 0，100% 用分类器损失（L_ce）训练，让模型专注于分类任务
        #中间过程：lambda_ 从 1 线性降到 0，平滑过渡，这就是「课程学习」—— 先学简单的（特征对齐），再学难的（分类）
        lambda_ = 1 - (epoch / num_epochs) ** 1

        # Training loop
        for data in train_loader:
            mri_, pet_, csf_, label_ = data
            optimizer.zero_grad()

            # Forward pass and loss computation
            loss, outputs, _ = model(mri=mri_, pet=pet_, csf=csf_, label=label_, lambda_=lambda_)
            mixed_loss = loss  # Assuming 'loss' is the mixed loss

            # Backward pass and optimization
            loss.backward()
            optimizer.step()

            # Update running losses
            running_mixed_loss += mixed_loss.item()
            _, predicted_train = torch.max(outputs, 1)
            correct_train += (predicted_train == label_).sum().item()

        # Calculate training accuracy and average loss
        train_accuracy = 100 * correct_train / len(train_loader.dataset)
        train_loss = running_mixed_loss / len(train_loader)


        # Validation loop
        model.eval()
        correct_val = 0
        valid_classifier_loss = 0.0

        with torch.no_grad():
            for data in val_loader:
                mri_, pet_, csf_, label_ = data

                # Forward pass and loss computation
                _, outputs, loss_ce = model(mri=mri_, pet=pet_, csf=csf_, label=label_, lambda_=lambda_)
                valid_classifier_loss += loss_ce.item()  # Assuming 'loss_ce' is the classifier loss
                _, predicted_val = torch.max(outputs, 1)
                correct_val += (predicted_val == label_).sum().item()

        # Calculate validation accuracy and average loss
        val_acc = 100 * correct_val / len(val_loader.dataset)
        avg_valid_classifier_loss = valid_classifier_loss / len(val_loader)


        # Save model if it has the best validation loss
        if avg_valid_classifier_loss < best_val_loss:
            best_val_loss = avg_valid_classifier_loss
            torch.save(model.state_dict(), 'checkpoint.pt')
            print("-------------------------------------Model has been saved-------------------------------------")

        # Logging
        print(
            f'Epoch {epoch + 1}, Train Loss: {train_loss:.2f}, '
            f'Val Loss: {valid_classifier_loss:.2f}, '
            f'Train Acc: {train_accuracy:.2f}%, Val Acc: {val_acc:.2f}%, Best Loss: {best_val_loss:.2f}'
        )


