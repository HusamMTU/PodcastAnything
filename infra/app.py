#!/usr/bin/env python3
"""CDK app entrypoint for Podcast Anything."""
from __future__ import annotations

import os

import aws_cdk as cdk

from podcast_anything_infra.stack import PodcastAnythingStack


def main() -> None:
    app = cdk.App()

    region = os.environ.get("AWS_REGION", "us-east-1")
    account = os.environ.get("CDK_DEFAULT_ACCOUNT")

    PodcastAnythingStack(
        app,
        "PodcastAnythingStack",
        env=cdk.Environment(account=account, region=region),
    )

    app.synth()


if __name__ == "__main__":
    main()
