"""Owner-run private membership/reference seed; no account creation or email sending.

The invoking operator needs data roles at only the three indicated seed scopes.
Production API/worker keep their separate managed-identity permissions.
"""
from pathlib import Path
import argparse
import json

from provision import check, load_config, write_private


def owner_seed_blobs(config, credential):
    """Operator-only transfer tuning; preserve AzureBlobStore's immutable writes.

    The local connection timed out on the 30-MiB single archive PUT. Use the
    documented block upload controls; production runtime clients are unchanged.
    https://learn.microsoft.com/azure/storage/blobs/storage-blobs-tune-upload-download-python
    """
    from azure.storage.blob import BlobServiceClient
    from pricing_web.artifacts import AzureBlobStore

    class OwnerSeedBlobStore(AzureBlobStore):
        def __init__(self):
            service = BlobServiceClient(
                account_url=f'https://{config["storage"]}.blob.core.windows.net/',
                credential=credential, max_single_put_size=1024 * 1024,
                max_block_size=1024 * 1024, connection_timeout=15, read_timeout=30,
                retry_total=0, retry_connect=0, retry_read=0, retry_status=0)
            self.container = service.get_container_client(config["inputs"])
            self.read_containers = [self.container]

    return OwnerSeedBlobStore()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--members", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--promotion", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    for path in (args.members, args.output):
        if path.resolve().is_relative_to(root): raise ValueError("Private inputs/output must stay outside the repository")
    if args.members.stat().st_mode & 0o077: raise ValueError("Membership input requires mode 0600")
    c = load_config(args.config)
    # The installed az CLI rejects get-access-token with BOTH --tenant and
    # --subscription. Validate the exact tenant via the scoped account read, then
    # request tokens with the explicit subscription alone; never use CLI default.
    check(c)
    members = json.loads(args.members.read_text())
    if len(members["users"]) != 2 or len({m["uid"] for m in members["users"]}) != 2:
        raise ValueError("Exactly two distinct private UIDs are required")
    if {u["role"] for u in members["users"]} != {"analyst", "reviewer"}:
        raise ValueError("A distinct analyst and reviewer are required")
    from azure.identity import AzureCliCredential
    from pricing_web.store import AzureStore
    from pricing_web.reference import provision_membership, seed_reference
    from pricing_web.auth import identity_key
    credential = AzureCliCredential(subscription=c["subscription_id"])
    store = AzureStore(f'https://{c["storage"]}.table.core.windows.net/', credential)
    blobs = owner_seed_blobs(c, credential)
    issuer = "https://securetoken.google.com/" + c["firebase_project"]
    results = []
    for member in members["users"]:
        caps = ["read", "upload", "edit", "train", "compare", "submit"] if member["role"] == "analyst" else ["read", "review", "publish"]
        old = store.get("identity", identity_key(issuer, member["uid"]), "membership")
        if old:
            current = old.data.get("memberships", {}).get(members["workspace"])
            expected = {"role": member["role"], "capabilities": sorted(caps), "enabled": True}
            if current != expected: raise ValueError("Existing membership differs; explicit reviewed update required")
        else:
            provision_membership(store, issuer, member["uid"], members["workspace"], caps, member["role"])
        results.append({"role": member["role"], "present": True})
    seed = seed_reference(store, blobs, members["workspace"], args.bundle, args.promotion, "owner-reference-seed-v1")
    write_private(args.output, {"membership_count": len(results), "memberships": results, "reference": seed,
                               "accounts_created": False, "training_started": False})
    print(json.dumps({"membership_count": len(results), "reference_seeded": True}))


if __name__ == "__main__": main()
