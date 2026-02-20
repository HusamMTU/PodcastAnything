"""CDK stack for Podcast Anything (Phase 1)."""
from __future__ import annotations

import os
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as sfn_tasks
from constructs import Construct


class PodcastAnythingStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        project_root = Path(__file__).resolve().parents[2]
        src_path = project_root / "src"
        layer_path = project_root / "infra" / "layers"

        bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID")
        if not bedrock_model_id:
            raise ValueError("BEDROCK_MODEL_ID must be set when synthesizing the CDK app.")

        mp_bucket = os.environ.get("MP_BUCKET")
        if not mp_bucket:
            raise ValueError("MP_BUCKET must be set when synthesizing the CDK app.")

        polly_voice_id = os.environ.get("POLLY_VOICE_ID", "Joanna")

        bucket = s3.Bucket(
            self,
            "ArtifactsBucket",
            bucket_name=mp_bucket,
            versioned=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            auto_delete_objects=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        common_env = {
            "MP_BUCKET": bucket.bucket_name,
            "BEDROCK_MODEL_ID": bedrock_model_id,
            "POLLY_VOICE_ID": polly_voice_id,
        }

        deps_layer = lambda_.LayerVersion(
            self,
            "PythonDepsLayer",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            code=lambda_.Code.from_asset(
                str(layer_path),
                bundling=cdk.BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_11.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output/python",
                    ],
                ),
            ),
            description="Requests + BeautifulSoup for article fetching.",
        )

        fetch_article_fn = lambda_.Function(
            self,
            "FetchArticleFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="podcast_anything.handlers.fetch_article.handler",
            code=lambda_.Code.from_asset(str(src_path)),
            memory_size=512,
            timeout=cdk.Duration.seconds(30),
            environment=common_env,
            layers=[deps_layer],
        )

        rewrite_script_fn = lambda_.Function(
            self,
            "RewriteScriptFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="podcast_anything.handlers.rewrite_script.handler",
            code=lambda_.Code.from_asset(str(src_path)),
            memory_size=512,
            timeout=cdk.Duration.seconds(60),
            environment=common_env,
        )

        generate_audio_fn = lambda_.Function(
            self,
            "GenerateAudioFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="podcast_anything.handlers.generate_audio.handler",
            code=lambda_.Code.from_asset(str(src_path)),
            memory_size=1024,
            timeout=cdk.Duration.seconds(60),
            environment=common_env,
        )

        bucket.grant_read_write(fetch_article_fn)
        bucket.grant_read_write(rewrite_script_fn)
        bucket.grant_read_write(generate_audio_fn)

        bedrock_policy = iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=["*"],
        )
        rewrite_script_fn.add_to_role_policy(bedrock_policy)

        polly_policy = iam.PolicyStatement(
            actions=["polly:SynthesizeSpeech"],
            resources=["*"],
        )
        generate_audio_fn.add_to_role_policy(polly_policy)

        fetch_step = sfn_tasks.LambdaInvoke(
            self,
            "FetchArticleStep",
            lambda_function=fetch_article_fn,
            payload=sfn.TaskInput.from_json_path_at("$"),
            output_path="$.Payload",
        )
        rewrite_step = sfn_tasks.LambdaInvoke(
            self,
            "RewriteScriptStep",
            lambda_function=rewrite_script_fn,
            payload=sfn.TaskInput.from_json_path_at("$"),
            output_path="$.Payload",
        )
        generate_step = sfn_tasks.LambdaInvoke(
            self,
            "GenerateAudioStep",
            lambda_function=generate_audio_fn,
            payload=sfn.TaskInput.from_json_path_at("$"),
            output_path="$.Payload",
        )

        state_machine = sfn.StateMachine(
            self,
            "PipelineStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(
                fetch_step.next(rewrite_step).next(generate_step)
            ),
            timeout=cdk.Duration.minutes(10),
        )

        cdk.CfnOutput(self, "ArtifactsBucketName", value=bucket.bucket_name)
        cdk.CfnOutput(self, "FetchArticleFnName", value=fetch_article_fn.function_name)
        cdk.CfnOutput(self, "RewriteScriptFnName", value=rewrite_script_fn.function_name)
        cdk.CfnOutput(self, "GenerateAudioFnName", value=generate_audio_fn.function_name)
        cdk.CfnOutput(self, "PipelineStateMachineArn", value=state_machine.state_machine_arn)
