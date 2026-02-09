#!/usr/bin/env python3
"""CDK app entrypoint for the ML Publication pipeline."""
from __future__ import annotations

import os

import aws_cdk as cdk

from ml_publication_infra.stack import MLPipelineStack


def main() -> None:
    app = cdk.App()

    region = os.environ.get("AWS_REGION", "us-east-1")
    account = os.environ.get("CDK_DEFAULT_ACCOUNT")

    MLPipelineStack(
        app,
        "MlPublicationPipeline",
        env=cdk.Environment(account=account, region=region),
    )

    app.synth()


if __name__ == "__main__":
    main()
