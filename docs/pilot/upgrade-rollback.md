# Upgrade and Rollback

Pin every pilot deployment to a package version or container digest. Do not use
`latest`.

## Workstation

Record the current version, create a backup, and install the candidate version.
If acceptance fails, reinstall the previous image or package version and repeat
the health and client checks.

## Docker Compose

Update the pinned image, then run:

```bash
docker compose pull cutctx-proxy
docker compose up -d cutctx-proxy
docker compose ps
```

For rollback, restore the previous image digest in the Compose file, run
`docker compose up -d cutctx-proxy`, and restore the pre-upgrade data backup
when the release changed persistent state.

## Kubernetes

```bash
kubectl set image deployment/cutctx-proxy cutctx-proxy=IMAGE_DIGEST -n cutctx
kubectl rollout status deployment/cutctx-proxy -n cutctx
kubectl rollout undo deployment/cutctx-proxy -n cutctx
```

## Helm

Use `helm upgrade` with the pinned image tag or digest. Record the prior
revision from `helm history`, then use `helm rollback RELEASE REVISION` when a
rollback is required.

Rollback when readiness fails, supported provider semantics regress, routing
selects an unsafe model, license validation fails for a valid pilot license, or
the operator cannot explain a material data discrepancy. Record the previous
image, trigger, owner, and acceptance result.

