import os
import numpy as np
import matplotlib.pyplot as plt

def get_lmbench_data(filename):
    time_list = {}
    lmbench_dict = {
        'Simple read': 'read',
        'Simple open/close': 'open',
        'Select on 500 fd\'s': 'select',
        'Signal handler installation': 'sig install',
        'Signal handler overhead:': 'sig hndl',
        'Process fork+exit': 'fork',
        'Process fork+/bin/sh -c': 'shell'
    }
    
    for line in open(filename):
        line = line.strip()
        for key in lmbench_dict:
            if line.startswith(key):
                time_value = float(line.split()[-2])
                kind_name = lmbench_dict[key]
                time_list[kind_name] = time_list.get(kind_name, [])
                time_list[kind_name].append(time_value)
    
    # print(time_list)

    time_dict = {}
    for key, value in time_list.items():
        value.sort()
        value = value[1:-1]
        time_dict[key] = sum(value)/len(value)

    # print(time_dict)
    return time_dict

def get_unixbench_data(filename):
    count_list = {}
    kind = None
    for line in open(filename):
        line = line.strip()
        if line.startswith('execute'):
            kind = line.split()[-1]
        elif line.startswith('COUNT'):
            count_value = float(line.split('|')[1])
            count_list[kind] = count_list.get(kind, [])
            count_list[kind].append(count_value)
    
    # print(count_list)

    time_dict = {}
    for key, value in count_list.items():
        if key != 'shell8':
            value.sort()
            value = value[1:-1]
        time_value = sum([1/v for v in value])/len(value)
        time_dict[key] = time_value

    time_dict.pop('syscall')
    
    # print(time_dict)
    return time_dict

def draw_history(store_path, history_list, file_list, base_value):
    plt.clf()
    for history, file in zip(history_list, file_list):
        for i in range(len(history)):
            history[i] -= base_value[i]
            history[i] /= base_value[i]
            history[i] *= 100
        plt.plot(history, label=file)
    plt.legend()
    plt.savefig(store_path)

def collect_bench_data(folder):
    lm_type = ['read', 'open', 'select', 'sig install', 'sig hndl', 'fork', 'shell']
    lmbench_entry = {lm_key:[] for lm_key in lm_type}
    lm_history = []
    lm_history_file = []

    unix_type = ['dhrystone', 'whetstone', 'execl', 'pipe', 'context', 'spawn', 'shell1', 'shell8']
    unixbench_entry = {unix_key:[] for unix_key in unix_type}
    unix_history = []
    unix_history_file = []

    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if filename.startswith('lmbench'):
            time_dict = get_lmbench_data(file_path)
            history = []
            for key in lm_type:
                history.append(time_dict[key])
            lm_history.append(history)
            lm_history_file.append(filename)

            for key in lmbench_entry:
                lmbench_entry[key].append(time_dict[key])
        elif filename.startswith('unixbench'):
            time_dict = get_unixbench_data(file_path)
            history = []
            for key in unix_type:
                history.append(time_dict[key])
            unix_history.append(history)
            unix_history_file.append(filename)

            for key in unixbench_entry:
                unixbench_entry[key].append(time_dict[key])
    
    draw_history(os.path.join(folder, 'log-lmbench'), lm_history, lm_history_file, [8.33335, 188.67975, 777.64285, 13.32115, 94.8, 14419.6, 87632.6])
    draw_history(os.path.join(folder, 'log-unixbench'), unix_history, unix_history_file, [2.721776120918326e-07, 0.010375717171681351, 0.0008525149190110827, 5.455497369454326e-06, 4.808945186918035e-05, 0.0003734129947722181, 0.012195121951219513, 0.1])

    lmbench_time_dict = {}
    for key, value in lmbench_entry.items():
        if len(value) >2:
            value.sort()
            value = value[1:-1]
        if len(value) > 0:
            lmbench_time_dict[key] = sum(value)/len(value)
        else:
            lmbench_time_dict[key] = 0
    # print(lmbench_entry)
    # print(lmbench_time_dict)

    unixbench_time_dict = {}
    for key, value in unixbench_entry.items():
        if key != 'shell8' and len(value) >2:
            value.sort()
            value = value[1:-1]
        if len(value) > 0:
            unixbench_time_dict[key] = sum(value)/len(value)
        else:
            unixbench_time_dict[key] = 0
    # print(unixbench_entry)
    # print(unixbench_time_dict)

    return lmbench_time_dict, unixbench_time_dict

def data_draw(dicts, draw_name, prot_type):
    def pad(string):
        return f"{string}{' '*(12-len(string))}"

    keys = list(dicts[0].keys())
    keys.append('ave')
    
    print(pad('name'), end='')
    for key in keys:
        print(pad(f'{key}'), end='')
    print()

    values = [list(d.values()) for d in dicts]
    for value in values:
        value.append(sum(value)/len(value))

    x = np.arange(len(keys))
    width = 0.1

    fig, ax = plt.subplots(figsize=(10, 6))

    for i, (value, prot) in enumerate(zip(values, prot_type)):
        print(pad(f'{prot}'), end='')
        for v in value:
            print(pad(f'{v:.2f}'), end='')
        print()
        ax.bar(x + i * width - width * 2, value, width, label=prot)
    print()

    ax.set_xlabel('Keys')
    ax.set_ylabel('Values')
    ax.set_title('Comparison of Multiple Dictionaries')
    ax.set_xticks(x)
    ax.set_xticklabels(keys)
    ax.legend()

    plt.tight_layout()
    fig.savefig(draw_name)



def prot_data_collect():
    prot_time_dict = []

    current_path = os.path.dirname(os.path.abspath(__file__))
    prot_type = ['none', 'ra', 'fp', 'non-ctrl', 'full']
    for prot_name in prot_type:
        folder_path = os.path.join(current_path, prot_name)
        lmbench_time_dict, unixbench_time_dict = collect_bench_data(folder_path)
        prot_time_dict.append({
            'lmbench': lmbench_time_dict,
            'unixbench': unixbench_time_dict
        })

    for prot_dict in prot_time_dict[1:]:
        for bench_name in prot_dict.keys():
            bench_value = prot_dict[bench_name]
            for kind in bench_value.keys():
                none_value = prot_time_dict[0][bench_name][kind]
                if bench_value[kind] != 0:
                    bench_value[kind] = (bench_value[kind] - none_value)/bench_value[kind]*100
                else:
                    bench_value[kind] = (bench_value[kind] - none_value)/none_value*100
    
    data_draw([d['lmbench'] for d in prot_time_dict[1:]], os.path.join(current_path, 'lmbench'), prot_type[1:])
    data_draw([d['unixbench'] for d in prot_time_dict[1:]], os.path.join(current_path, 'unixbench'), prot_type[1:])

if __name__ == "__main__":
    prot_data_collect()

