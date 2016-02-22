m = dlmread('cifar_benchmark');

colors = [
0.1 0.5 0.2
0.05 0.05 1
0.9 0.05 0
0.9 0.8 0.05
0.9 0.05 1
0.05 0 0
0.05 0.9 0
0.05 0.9 1
]

%plot average iter time/node number and speedup/node
node_num_arr = unique(m(:, 2))';
time_cost = zeros(1, numel(node_num_arr))
for i = 1:numel(node_num_arr)
    time_cost(i) = mean(m(m(:, 2) == node_num_arr(i), end))
end
figure('position', [100, 100, 350, 300])
plot(node_num_arr, time_cost, 'r-', 'LineWidth', 1.2)
axis([1 8 20 180]);
legend('MXNet');
grid on
ylabel('Average Epoch Time (ms)')
xlabel('Node Number')


figure('position', [200, 100, 350, 300])
plot(node_num_arr, time_cost(1)./time_cost, 'r-', 'LineWidth', 1.2)
hold on
plot(node_num_arr, node_num_arr, 'b-.', 'LineWidth', 1.2)
legend('MXNet','Perfect','Location','northwest');
axis([1 8 1 8]);
grid on
ylabel('Accelerating Ratio')
xlabel('Node Number')
hold off

%plot training_acc/epoch
figure('position', [200, 200, 350, 300])
for i = 1:numel(node_num_arr)
    singlerun = m(m(:, 2) == node_num_arr(i), :)
    plot(singlerun(:, 1) + 1, singlerun(:, 5), 'LineWidth', 0.8, 'Color', colors(i, :))
    hold on
end
legend('Node=1', 'Node=2', 'Node=3', 'Node=4', 'Node=5', 'Node=6', 'Node=7', 'Node=8','Location','southeast')
axis([1 20 0.4 1]);
grid on
ylabel('Training Accuracy')
xlabel('Epoch Number')
hold off

%plot validation_acc/epoch
figure('position', [200, 300, 350, 300])
for i = 1:numel(node_num_arr)
    singlerun = m(m(:, 2) == node_num_arr(i), :)
    plot(singlerun(:, 1) + 1, singlerun(:, 4), 'LineWidth', 0.8, 'Color', colors(i, :))
    hold on
end
legend('Node=1', 'Node=2', 'Node=3', 'Node=4', 'Node=5', 'Node=6', 'Node=7', 'Node=8','Location','southeast')
axis([1 20 0.2 1]);
grid on
ylabel('Validation Accuracy')
xlabel('Epoch Number')
hold off

%plot training_acc/time-spent
figure('position', [300, 300, 350, 300])

for i = 1:numel(node_num_arr)
    singlerun = m(m(:, 2) == node_num_arr(i), :)
    plot(cumsum(singlerun(:, end)), singlerun(:, 5), 'LineWidth', 0.8, 'Color', colors(i, :))
    hold on
end
legend('Node=1', 'Node=2', 'Node=3', 'Node=4', 'Node=5', 'Node=6', 'Node=7', 'Node=8','Location','southeast')
axis([0 3000 0.45 1]);
grid on
ylabel('Training Accuracy')
xlabel('Time Spent')
hold off


%plot valid_acc/time-spent
figure('position', [300, 400, 350, 300])

for i = 1:numel(node_num_arr)
    singlerun = m(m(:, 2) == node_num_arr(i), :)
    plot(cumsum(singlerun(:, end)), singlerun(:, 4), 'LineWidth', 0.8, 'Color', colors(i, :))
    hold on
end
legend('Node=1', 'Node=2', 'Node=3', 'Node=4', 'Node=5', 'Node=6', 'Node=7', 'Node=8','Location','southeast')
axis([0 3000 0.45 1]);
grid on
ylabel('Validation Accuracy')
xlabel('Time Spent')
hold off

