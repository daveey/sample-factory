import os
import pickle
import sys
from os.path import join
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

from utils.utils import log, ensure_dir_exists, experiments_dir

# zhehui
# matplotlib.rcParams['text.usetex'] = True
matplotlib.rcParams['mathtext.fontset'] = 'cm'
# matplotlib.rcParams['font.family'] = 'serif'
matplotlib.rcParams['font.size'] = 8

plt.rcParams['figure.figsize'] = (5.5, 2.3) #(2.5, 2.0) 7.5， 4


B = int(1e9)

EXPERIMENTS = {
    'doom_battle': dict(is_pbt=False, dir='doom_battle_appo_v56_4p', key='0_aux/avg_reward', x_ticks=[0, B, 2*B, 3*B, 4*B], max_x=4*B, y_ticks=[0, 10, 20, 30, 40, 50], x_label='Env. frames, skip=4', title='Battle', baselines=((33, 'DFP'), (35, 'DFP+CV')), legend='SampleFactory'),
    'doom_battle2': dict(is_pbt=False, dir='doom_battle2_appo_v65_fs4', key='0_aux/avg_true_reward', x_ticks=[0, B, 2*B, 3*B], max_x=3*B, y_ticks=[0, 5, 10, 15, 20, 25], x_label='Env. frames, skip=4', title='Battle2', baselines=((17, 'DFP'), ), legend='SampleFactory'),
    'doom_deathmatch': dict(is_pbt=True, dir='doom_bots_v63_pbt', key='0_aux/avg_true_reward', x_ticks=[0, B//2, B, 3*B//2, 2*B, 5*B//2], max_x=5*B//2, y_ticks=[0, 20, 40, 60, 80], x_label='Env. frames, skip=2', title='Deathmatch vs bots', baselines=((12.6, 'Avg. scripted bot'), (22, 'Best scripted bot')), legend='Population mean'),
    'doom_duel': dict(is_pbt=True, dir='paper_doom_duel_bots_v65_fs2', key='0_aux/avg_true_reward', x_ticks=[0, B//2, B, 3*B//2, 2*B, 5*B//2], max_x=5*B//2, y_ticks=[0, 10, 20, 30, 40], x_label='Env. frames, skip=2', title='Duel vs bots', baselines=((3.66, 'Avg. scripted bot'), (5, 'Best scripted bot')), legend='Population mean'),
}

PLOT_NAMES = dict(
    # doom_my_way_home='Find My Way Home',
    # doom_deadly_corridor='Deadly Corridor',
    # doom_defend_the_center='Defend the Center',
    # doom_defend_the_line='Defend the Line',
    # doom_health_gathering='Health Gathering',
    # doom_health_gathering_supreme='Health Gathering Supreme',
)


def extract(env, experiments):
    # scalar_accumulators = [EventAccumulator(str(dpath / dname / subpath)).Reload().scalars
    #                        for dname in os.listdir(dpath) if dname != FOLDER_NAME and dname in hide_file]

    scalar_accumulators = [EventAccumulator(experiment_dir).Reload().scalars for experiment_dir in experiments]

    # Filter non event files
    scalar_accumulators = [scalar_accumulator for scalar_accumulator in scalar_accumulators if scalar_accumulator.Keys()]

    # Get and validate all scalar keys
    # zhehui sorted(scalar_accumulator.Keys())
    all_keys = [tuple(sorted(scalar_accumulator.Keys())) for scalar_accumulator in scalar_accumulators]
    # assert len(set(all_keys)) == 1, "All runs need to have the same scalar keys. There are mismatches in {}".format(all_keys)
    keys = all_keys[0]

    def all_accumulators_have_this_key(key):
        for scalar_accumulator in scalar_accumulators:
            if key not in scalar_accumulator.Keys():
                log.debug('Not all of the accumulators have key %s', key)
                return False

        return True

    keys = [key for key in keys if all_accumulators_have_this_key(key)]

    all_scalar_events_per_key = [[scalar_accumulator.Items(key) for scalar_accumulator in scalar_accumulators] for key in keys]

    # Get and validate all steps per key
    # sorted(all_scalar_events) sorted(scalar_events)
    x_per_key = [[tuple(scalar_event.step for scalar_event in sorted(scalar_events)) for scalar_events in sorted(all_scalar_events)]
                         for all_scalar_events in all_scalar_events_per_key]


    # zhehui
    # import linear interpolation
    # all_steps_per_key = tuple(step_id*1e6 for step_id in range(1e8/1e6))

    # modify_all_steps_per_key = tuple(int(step_id*1e6) for step_id in range(1, int(1e8/1e6 + 1)))
    plot_step = int(1e7)
    max_x = EXPERIMENTS[env]['max_x']
    all_steps_per_key = [[tuple(int(step_id) for step_id in range(0, max_x, plot_step)) for scalar_events in sorted(all_scalar_events)]
                         for all_scalar_events in all_scalar_events_per_key]

    for i, all_steps in enumerate(all_steps_per_key):
        assert len(set(all_steps)) == 1, "For scalar {} the step numbering or count doesn't match. Step count for all runs: {}".format(
            keys[i], [len(steps) for steps in all_steps])

    steps_per_key = [all_steps[0] for all_steps in all_steps_per_key]

    # Get and average wall times per step per key
    # wall_times_per_key = [np.mean([tuple(scalar_event.wall_time for scalar_event in scalar_events) for scalar_events in all_scalar_events], axis=0)
    #                       for all_scalar_events in all_scalar_events_per_key]

    # Get values per step per key
    values_per_key = [[[scalar_event.value for scalar_event in scalar_events] for scalar_events in all_scalar_events]
                      for all_scalar_events in all_scalar_events_per_key]

    true_reward_key = EXPERIMENTS[env]['key']
    key_idx = keys.index(true_reward_key)
    values = values_per_key[key_idx]

    x = steps_per_key[key_idx]
    x_steps = x_per_key[key_idx]

    interpolated_y = [[] for _ in values]

    for i in range(len(values)):
        idx = 0

        values[i] = values[i][2:]
        x_steps[i] = x_steps[i][2:]

        assert len(x_steps[i]) == len(values[i])
        for x_idx in x:
            while idx < len(x_steps[i]) and x_steps[i][idx] < x_idx:
                idx += 1
                # log.debug('i: %d, x_idx: %d, idx: %d, len %d', i, x_idx, idx, len(x_steps[i]))

            if idx == len(x_steps[i]):
                break

            if x_idx == 0:
                interpolated_value = values[i][idx]
            elif idx < len(values[i]) - 1:
                interpolated_value = (values[i][idx] + values[i][idx + 1]) / 2
            else:
                interpolated_value = values[i][idx]

            interpolated_y[i].append(interpolated_value)

        x = x[:len(interpolated_y[i])]
        assert len(interpolated_y[i]) == len(x)

    log.debug('Key values: %r', interpolated_y[0][:30])

    min_length = len(x)
    for i in range(len(values)):
        log.debug('Values for seed %d truncated from %d to %d', i, len(interpolated_y[i]), min_length)
        interpolated_y[i] = interpolated_y[i][:min_length]

    interpolated_keys = dict()
    interpolated_keys[true_reward_key] = (x, interpolated_y)

    return interpolated_keys


def aggregate(env, experiments, count, ax):
    print("Started aggregation {}".format(env))

    curr_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = join(curr_dir, 'cache_complex_envs')
    cache_env = join(cache_dir, env)

    if os.path.isdir(cache_env):
        with open(join(cache_env, f'{env}.pickle'), 'rb') as fobj:
            interpolated_keys = pickle.load(fobj)
    else:
        cache_env = ensure_dir_exists(cache_env)
        interpolated_keys = extract(env, experiments)
        with open(join(cache_env, f'{env}.pickle'), 'wb') as fobj:
            pickle.dump(interpolated_keys, fobj)

    for key in interpolated_keys.keys():
        plot(env, key, interpolated_keys[key], ax, count)


def plot(env, key, interpolated_key, ax, count):
    title_text = EXPERIMENTS[env]['title']
    ax.set_title(title_text, fontsize=8)

    x, y = interpolated_key

    y_np = [np.array(yi) for yi in y]
    y_np = np.stack(y_np)

    if env == 'doom_deadly_corridor':
        # fix reward scale
        y_np *= 100

    y_mean = np.mean(y_np, axis=0)
    y_std = np.std(y_np, axis=0)
    y_plus_std = np.minimum(y_mean + y_std, y_np.max())
    y_minus_std = y_mean - y_std

    y_max = np.max(y_np, axis=0)

    # Configuration
    # fig, ax = plt.subplots()

    def mkfunc(x, pos):
        if x >= 1e9:
            return '%dB' % int(x * 1e-9)
        elif x >= 1e6:
            return '%dM' % int(x * 1e-6)
        elif x >= 1e3:
            return '%dK' % int(x * 1e-3)
        else:
            return '%d' % int(x)

    mkformatter = matplotlib.ticker.FuncFormatter(mkfunc)
    # ax.xaxis.set_major_formatter(mkformatter)

    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_linewidth(1.0)

    # xlabel_text = env.replace('_', ' ').title()
    # plt.xlabel(xlabel_text, fontsize=8)
    # zhehui
    # if they are bottom plots, add Environment Frames
    ax.set_xlabel(EXPERIMENTS[env]['x_label'], fontsize=8)

    if count == 0:
        ax.set_ylabel('Kills per episode', fontsize=8)

    ax.set_xticks(EXPERIMENTS[env]['x_ticks'])
    ax.set_yticks(EXPERIMENTS[env]['y_ticks'])

    # hide tick of axis
    ax.xaxis.tick_bottom()
    ax.yaxis.tick_left()
    ax.tick_params(which='major', length=0)

    ax.grid(color='#B3B3B3', linestyle='-', linewidth=0.25, alpha=0.2)
    # ax.xaxis.grid(False)

    x_delta = 0.05 * x[-1]
    ax.set_xlim(xmin=-x_delta, xmax=x[-1] + x_delta)

    y_delta = 0.05 * np.max(y_max)
    ax.set_ylim(ymin=min(np.min(y_mean) - y_delta, 0.0), ymax=np.max(y_max) + y_delta)
    # plt.grid(False)

    plt.ticklabel_format(style='sci', axis='x', scilimits=(8, 9))
    ax.ticklabel_format(style='plain', axis='y', scilimits=(0, 0))

    marker_size = 0
    lw = 1.0
    lw_max = 0.7
    lw_baseline = 0.7

    blue = '#1F77B4'
    orange = '#FF7F0E'
    green = '#2CA02C'

    sf_plot, = ax.plot(x, y_mean, color=blue, label=EXPERIMENTS[env]['legend'], linewidth=lw, antialiased=True)
    ax.fill_between(x, y_minus_std, y_plus_std, color=blue, alpha=0.25, antialiased=True, linewidth=0.0)

    if EXPERIMENTS[env]['is_pbt']:
        ax.plot(x, y_max, color='#d62728', label='Population best', linewidth=lw_max, antialiased=True)

    if 'baselines' in EXPERIMENTS[env]:
        colors = [green, orange]

        baselines = EXPERIMENTS[env]['baselines']
        for baseline_i, baseline in enumerate(baselines):
            baseline_color = colors[baseline_i]
            baseline_y, baseline_name = baseline
            ax.plot([x[0], x[-1]], [baseline_y, baseline_y], color=baseline_color, label=baseline_name, linewidth=lw_baseline, antialiased=True, linestyle='--')

    # ax.legend(prop={'size': 6}, loc='lower right')

    # plt.set_tight_layout()
    # plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=1, wspace=0)
    # plt.margins(0, 0)

    # plot_name = f'{env}_{key.replace("/", " ")}'
    # plt.savefig(os.path.join(os.getcwd(), f'../final_plots/reward_{plot_name}.pdf'), format='pdf', bbox_inches='tight', pad_inches=0)


def main():
    all_experiment_dirs_list = [join(experiments_dir(), v['dir']) for k, v in EXPERIMENTS.items()]
    for experiment_dir in all_experiment_dirs_list:
        log.debug('Experiment dir: %s', experiment_dir)

    log.debug('Total: %d', len(all_experiment_dirs_list))

    for env, details in EXPERIMENTS.items():
        env_dir = details['dir']
        env_dir = join(experiments_dir(), env_dir)
        event_files = Path(env_dir).rglob('*.tfevents.*')
        event_files = list(event_files)
        log.info('Event files: %r', event_files)

        env_dirs = set()
        for event_file in event_files:
            env_dirs.add(os.path.dirname(event_file))

        EXPERIMENTS[env]['dirs'] = sorted(list(env_dirs))
        log.info('Env dirs for env %s is %r', env, env_dirs)

    EXPERIMENT_GROUPS = (('doom_battle', 'doom_battle2'), ('doom_deathmatch', 'doom_duel'))

    for group_i, exp_group in enumerate(EXPERIMENT_GROUPS):
        fig, (ax1, ax2) = plt.subplots(1, 2)
        ax = (ax1, ax2)

        count = 0
        for env in exp_group:
            experiments = EXPERIMENTS[env]['dirs']
            aggregate(env, experiments, count, ax[count])
            count += 1

        handles, labels = ax[-1].get_legend_handles_labels()
        lgd = fig.legend(handles, labels, bbox_to_anchor=(0.1, 0.88, 0.8, 0.2), loc='lower left', ncol=4, mode="expand", prop={'size': 6})

        lgd.set_in_layout(True)

        # zhehui
        # plt.show()
        # plot_name = f'{env}_{key.replace("/", " ")}'
        # plt.tight_layout()
        # plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=1, wspace=0)
        # plt.subplots_adjust(wspace=0.12, hspace=0.15)

        plt.tight_layout(rect=(0, 0, 1.0, 0.9))

        plt.margins(0, 0)
        plot_name = f'complex_envs_{group_i}'
        # plt.savefig(os.path.join(os.getcwd(), f'../final_plots/reward_{plot_name}.pdf'), format='pdf', bbox_inches='tight', pad_inches=0, )
        plt.savefig(os.path.join(os.getcwd(), f'../final_plots/reward_{plot_name}.pdf'), format='pdf', bbox_extra_artists=(lgd,))


    return 0


if __name__ == '__main__':
    sys.exit(main())
