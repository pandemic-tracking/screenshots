""" Main script to run image capture screenshots for state data pages. """

import io
import os
import sys

from loguru import logger
import pandas as pd
import requests
import yaml

from args import parser as screenshots_parser
from screenshotter import Screenshotter
from utils import S3Backup, SlackNotifier


_ALL_STATES = [
    'AK', 'AL', 'AR', 'AS', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA', 'GU', 'HI', 'IA', 'ID',
    'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MI', 'MN', 'MO', 'MP', 'MS', 'MT', 'NC', 'ND',
    'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'PR', 'RI', 'SC', 'SD', 'TN', 'TX',
    'UT', 'VA', 'VI', 'VT', 'WA', 'WI', 'WORLD', 'WV', 'WY', 'US', 'GL']


def states_from_args(args):
    # if states are user-specified, snapshot only those
    if args.states:
        logger.info(f'Snapshotting states {args.states}')
        return args.states.split(',')
    else:
        logger.info('Snapshotting all states')
        return _ALL_STATES


def config_dir_from_args(args):
    if args.core_urls:
        subdir = 'taco'
    elif args.crdt_urls:
        subdir = 'crdt'
    elif args.ltc_urls:
        subdir = 'ltc'
    elif args.vax_urls:
        subdir = 'vax'
    elif args.variant_urls:
        subdir = 'variants'
    elif args.bi_urls:
        subdir = 'bi'
    elif args.reinfections_urls:
        subdir = 'reinfections'
    elif args.waste_urls:
        subdir = 'waste'
    elif args.globalvax_urls:
        subdir = 'globalvax'

    return os.path.join(os.path.dirname(__file__), 'configs', subdir)


def slack_notifier_from_args(args):
    if args.slack_channel and args.slack_api_token:
        return SlackNotifier(args.slack_channel, args.slack_api_token)
    return None


# Return a small string describing which run this is.
def run_type_from_args(args):
    if args.core_urls:
        return 'core'
    elif args.crdt_urls:
        return 'CRDT'
    elif args.ltc_urls:
        return 'LTC'
    elif args.vax_urls:
        return 'vaccine'
    elif args.variant_urls:
        return 'variants'
    elif args.bi_urls:
        return 'bi'
    elif args.reinfections_urls:
        return 'reinfections'
    elif args.waste_urls:
        return 'waste'
    elif args.globalvax_urls:
        return 'globalvax'
    raise ValueError('no run type specified in args: %s' % args)


def main(args_list=None):
    if args_list is None:
        args_list = sys.argv[1:]
    args = screenshots_parser.parse_args(args_list)
    s3 = S3Backup(bucket_name=args.s3_bucket, s3_subfolder=args.s3_subfolder)
    config_dir = config_dir_from_args(args)
    slack_notifier = slack_notifier_from_args(args)
    run_type = run_type_from_args(args)
    screenshotter = Screenshotter(
        local_dir=args.temp_dir, s3_backup=s3,
        phantomjscloud_key=args.phantomjscloud_key,
        dry_run=args.dry_run, config_dir=config_dir)

    failed_states = []
    slack_failure_messages = []

    for state in states_from_args(args):
        errors = screenshotter.screenshot(
            state, args.which_screenshot, backup_to_s3=args.push_to_s3)
        if errors is None:
            continue
        for suffix, error in errors.items():
            logger.error(f'Error in {state} {suffix}: {error}')
            failed_states.append((state, suffix))
            if slack_notifier:
                slack_failure_messages.append(f'Error in {state} {suffix}: {error}')

    if failed_states:
        failed_states_str = ', '.join([':'.join(x) for x in failed_states])
        logger.error(f"Errored screenshot states for this {run_type} run: {failed_states_str}")
        if slack_notifier:
            slack_response = slack_notifier.notify_slack(
                f"Errored screenshot states for this {run_type} run: {failed_states_str}")
            # put the corresponding messages into a thread
            thread_ts = slack_response.get('ts')
            for detailed_message in slack_failure_messages:
                slack_notifier.notify_slack(detailed_message, thread_ts=thread_ts)

    else:
        logger.info("All attempted states successfully screenshotted")


if __name__ == "__main__":
    main()
