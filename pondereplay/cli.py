"""
PonDeReplay CLI - Replay Ethereum transactions with patched contract bytecode
"""
import json
import sys
from typing import Optional

import click
from dotenv import load_dotenv

from .replayer import TransactionReplayer, ReplayResult
from .batch import BatchReplayer, print_batch_report
from .etherscan import EtherscanError, get_contract_history
from .txlist import read_tx_hashes_from_file
from .utils import read_bytecode as _read_bytecode_util

load_dotenv()


@click.group()
@click.version_option()
def cli():
    """PonDeReplay: Replay transactions with patched contract bytecode"""
    pass


@cli.command()
@click.option(
    "--rpc-url",
    required=True,
    envvar="ETH_RPC_URL",
    help="Ethereum RPC URL (or set ETH_RPC_URL env var)",
)
@click.option(
    "--tx-hash",
    required=True,
    type=str,
    help="Transaction hash to replay (0x-prefixed)",
)
@click.option(
    "--contract-address",
    required=True,
    type=str,
    help="Contract address to patch (0x-prefixed)",
)
@click.option(
    "--bytecode-file",
    required=False,
    type=click.Path(exists=True),
    help="Path to new contract bytecode (hex string or JSON artifact)",
)
@click.option(
    "--bytecode-hex",
    required=False,
    type=str,
    help="Patched deployed contract bytecode as a 0x-prefixed hex string",
)
@click.option(
    "--fork-url",
    required=False,
    envvar="ETH_FORK_URL",
    help="Separate fork URL if different from RPC (defaults to RPC_URL)",
)
@click.option(
    "--output",
    type=click.Choice(["json", "text"]),
    default="json",
    help="Output format",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
def replay(
    rpc_url: str,
    tx_hash: str,
    contract_address: str,
    bytecode_file: Optional[str],
    bytecode_hex: Optional[str],
    fork_url: Optional[str],
    output: str,
    verbose: bool,
):
    """
    Replay a transaction with patched contract bytecode.
    
    This command:
    1. Fetches the original transaction details
    2. Forks the blockchain at the transaction's block
    3. Replaces the contract bytecode with the patched version
    4. Re-executes the transaction
    5. Reports all execution details
    """
    try:
        if verbose:
            click.echo("🔧 Initializing PonDeReplay...", err=True)
        
        bytecode = _resolve_bytecode_override(
            bytecode_file=bytecode_file, bytecode_hex=bytecode_hex
        )
        
        if verbose:
            if bytecode is None:
                click.echo("✓ No patched bytecode provided (using original bytecode)", err=True)
            else:
                click.echo(f"✓ Bytecode loaded ({len(bytecode) // 2} bytes)", err=True)
        
        # Create replayer
        fork_url = fork_url or rpc_url
        replayer = TransactionReplayer(rpc_url, fork_url)
        
        if verbose:
            click.echo(f"✓ Connected to {rpc_url}", err=True)
            click.echo(f"⏱️  Replaying transaction {tx_hash}...", err=True)
        
        # Replay transaction
        result = replayer.replay_transaction(
            tx_hash=tx_hash,
            contract_address=contract_address,
            new_bytecode=bytecode,
            verbose=verbose,
        )
        
        # Output results
        if output == "json":
            click.echo(json.dumps(result.to_dict(), indent=2))
        else:
            _print_text_output(result)
        
        if verbose:
            click.echo("✅ Replay completed successfully", err=True)
        
        sys.exit(0 if result.success else 1)
        
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command("replay-history")
@click.option(
    "--rpc-url",
    required=True,
    envvar="ETH_RPC_URL",
    help="Ethereum RPC URL (or set ETH_RPC_URL env var)",
)
@click.option(
    "--contract-address",
    required=True,
    type=str,
    help="Contract address to patch (0x-prefixed)",
)
@click.option(
    "--etherscan-api-key",
    required=False,
    envvar="ETHERSCAN_API_KEY",
    help="Etherscan API key (or set ETHERSCAN_API_KEY)",
)
@click.option(
    "--etherscan-network",
    required=False,
    type=click.Choice(["mainnet", "sepolia", "holesky"], case_sensitive=False),
    default="mainnet",
    show_default=True,
    help="Etherscan network to query",
)
@click.option(
    "--tx-list-file",
    required=False,
    type=click.Path(exists=True),
    help="Path to a file containing tx hashes (one per line) or JSON list",
)
@click.option(
    "--start-block",
    type=int,
    default=None,
    help="Starting block for history fetch (default: explorer/provider default)",
)
@click.option(
    "--end-block",
    type=int,
    default=None,
    help="Ending block for history fetch (default: explorer/provider default)",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Maximum number of txs to replay",
)
@click.option(
    "--bytecode-file",
    required=False,
    type=click.Path(exists=True),
    help="Path to patched contract bytecode (hex string or JSON artifact)",
)
@click.option(
    "--bytecode-hex",
    required=False,
    type=str,
    help="Patched deployed contract bytecode as a 0x-prefixed hex string",
)
@click.option(
    "--attack-tx",
    type=str,
    default=None,
    help="Expected attack transaction hash (0x-prefixed, for reporting)",
)
@click.option(
    "--output",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
def replay_history(
    rpc_url: str,
    contract_address: str,
    etherscan_api_key: Optional[str],
    etherscan_network: str,
    tx_list_file: Optional[str],
    start_block: Optional[int],
    end_block: Optional[int],
    limit: Optional[int],
    bytecode_file: Optional[str],
    bytecode_hex: Optional[str],
    attack_tx: Optional[str],
    output: str,
    verbose: bool,
):
    """
    Replay a contract's historical transactions with patched bytecode.

    Each transaction is replayed against the chain state at (block_number - 1),
    i.e. the block immediately before the original transaction.
    """
    try:
        if verbose:
            click.echo("🔧 Initializing history replay...", err=True)

        if bool(etherscan_api_key) == bool(tx_list_file):
            raise click.UsageError(
                "Provide exactly one history source: --etherscan-api-key or --tx-list-file"
            )

        bytecode = _resolve_bytecode_override(
            bytecode_file=bytecode_file, bytecode_hex=bytecode_hex
        )

        if verbose:
            if bytecode is None:
                click.echo(
                    "✓ No patched bytecode provided (using original bytecode per-tx)",
                    err=True,
                )
            else:
                click.echo(
                    f"✓ Bytecode loaded ({len(bytecode) // 2} bytes)", err=True
                )

        if etherscan_api_key:
            if verbose:
                click.echo(
                    f"🔍 Fetching transaction history from Etherscan ({etherscan_network})...",
                    err=True,
                )
            tx_hashes = get_contract_history(
                api_key=etherscan_api_key,
                contract_address=contract_address,
                network=etherscan_network,
                start_block=start_block,
                end_block=end_block,
                limit=limit,
                include_internal=True,
            )
        else:
            if verbose:
                click.echo(f"📄 Reading tx hashes from {tx_list_file}...", err=True)
            tx_hashes = read_tx_hashes_from_file(tx_list_file)  # type: ignore[arg-type]
            if limit is not None:
                tx_hashes = tx_hashes[:limit]

        if not tx_hashes:
            click.echo("No transactions found for the requested history source/range.")
            sys.exit(0)

        if verbose:
            click.echo(f"✓ Found {len(tx_hashes)} transactions", err=True)
            click.echo(f"🎬 Replaying {len(tx_hashes)} transactions...", err=True)

        batch = BatchReplayer(rpc_url)
        results = batch.replay_batch(
            tx_hashes=tx_hashes,
            contract_address=contract_address,
            new_bytecode=bytecode,
            verbose=verbose,
        )
        report = batch.generate_report(results, attack_tx=attack_tx, verbose=verbose)

        if output == "json":
            output_data = {
                "total": report["total"],
                "passed": report["passed"],
                "failed": report["failed"],
                "attack_tx_failed_as_expected": report.get(
                    "attack_tx_failed_as_expected", False
                ),
                "passed_txs": report["passed_txs"],
                "failed_txs": report["failed_txs"],
            }
            click.echo(json.dumps(output_data, indent=2))
        else:
            print_batch_report(report, attack_tx=attack_tx)

        sys.exit(0)

    except (EtherscanError, click.ClickException) as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option(
    "--rpc-url",
    required=True,
    envvar="ETH_RPC_URL",
    help="Ethereum RPC URL",
)
@click.argument("contract_address")
def bytecode(rpc_url: str, contract_address: str):
    """
    Fetch current bytecode of a contract
    """
    try:
        from web3 import Web3
        
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        code = w3.eth.get_code(contract_address)
        click.echo(code.hex())
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command("sanity-check")
@click.option(
    "--rpc-url",
    required=True,
    envvar="ETH_RPC_URL",
    help="Ethereum RPC URL (or set ETH_RPC_URL env var)",
)
@click.option(
    "--tx-hash",
    required=True,
    type=str,
    help="Transaction hash to check (0x-prefixed)",
)
@click.option(
    "--contract-address",
    required=True,
    type=str,
    help="Contract address (0x-prefixed)",
)
@click.option(
    "--output",
    type=click.Choice(["json", "text"]),
    default="json",
    help="Output format",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
def sanity_check(
    rpc_url: str,
    tx_hash: str,
    contract_address: str,
    output: str,
    verbose: bool,
):
    """
    Sanity check: verify replay mechanism works with original bytecode.
    
    This command:
    1. Fetches the original contract bytecode
    2. Replays the transaction with the original bytecode
    3. Compares the result with the original transaction receipt
    
    If this passes, the replay mechanism is working correctly and you can
    trust results from replaying with patched bytecode.
    """
    try:
        if verbose:
            click.echo("🔧 Initializing PonDeReplay...", err=True)
        
        # Create replayer
        replayer = TransactionReplayer(rpc_url)
        
        if verbose:
            click.echo(f"✓ Connected to {rpc_url}", err=True)
            click.echo(f"🧪 Running sanity check for {tx_hash}...", err=True)
        
        # Run sanity check
        result, matches = replayer.sanity_check(
            tx_hash=tx_hash,
            contract_address=contract_address,
            verbose=verbose,
        )
        
        # Output results
        if output == "json":
            output_data = {
                **result.to_dict(),
                "sanity_check_passed": matches,
            }
            click.echo(json.dumps(output_data, indent=2))
        else:
            _print_text_output(result)
            click.echo()
            if matches:
                click.echo("✅ SANITY CHECK PASSED - Replay mechanism is working correctly!")
            else:
                click.echo("❌ SANITY CHECK FAILED - Replay output doesn't match original!")
                click.echo("   There may be an issue with the replay mechanism.")
        
        if verbose:
            click.echo("✅ Sanity check completed", err=True)
        
        sys.exit(0 if matches else 1)
        
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command("batch-replay")
@click.option(
    "--rpc-url",
    required=True,
    envvar="ETH_RPC_URL",
    help="Ethereum RPC URL (or set ETH_RPC_URL env var)",
)
@click.option(
    "--contract-address",
    required=True,
    type=str,
    help="Contract address to scan and patch (0x-prefixed)",
)
@click.option(
    "--bytecode-file",
    required=True,
    type=click.Path(exists=True),
    help="Path to patched contract bytecode",
)
@click.option(
    "--bytecode-hex",
    required=False,
    type=str,
    help="Patched deployed contract bytecode as a 0x-prefixed hex string",
)
@click.option(
    "--start-block",
    type=int,
    default=0,
    help="Starting block for scan (default: 0)",
)
@click.option(
    "--end-block",
    type=int,
    default=None,
    help="Ending block for scan (default: latest)",
)
@click.option(
    "--attack-tx",
    type=str,
    default=None,
    help="Expected attack transaction hash (0x-prefixed, for reporting)",
)
@click.option(
    "--output",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
def batch_replay(
    rpc_url: str,
    contract_address: str,
    bytecode_file: str,
    bytecode_hex: Optional[str],
    start_block: int,
    end_block: int,
    attack_tx: str,
    output: str,
    verbose: bool,
):
    """
    Batch replay all transactions to a contract address with patched bytecode.
    
    This command:
    1. Scans the blockchain for all transactions to the contract
    2. Replays each one with the patched bytecode
    3. Generates a report showing which passed/failed
    """
    try:
        if verbose:
            click.echo("🔧 Initializing batch replayer...", err=True)
        
        bytecode = _resolve_bytecode_override(
            bytecode_file=bytecode_file, bytecode_hex=bytecode_hex
        )
        if bytecode is None:
            raise click.UsageError(
                "batch-replay requires patched bytecode via --bytecode-file or --bytecode-hex"
            )
        if verbose:
            click.echo(f"✓ Bytecode loaded ({len(bytecode) // 2} bytes)", err=True)
        
        # Create batch replayer
        batch = BatchReplayer(rpc_url)
        if verbose:
            click.echo(f"✓ Connected to {rpc_url}", err=True)
        
        # Scan for transactions
        if verbose:
            click.echo(f"🔍 Scanning for transactions to {contract_address}...", err=True)
        
        tx_hashes = batch.get_transactions_to_address(
            address=contract_address,
            start_block=start_block,
            end_block=end_block,
            verbose=verbose,
        )
        
        if verbose:
            click.echo(f"✓ Found {len(tx_hashes)} transactions", err=True)
        
        if not tx_hashes:
            click.echo("No transactions found for this address in the scanned range.")
            sys.exit(0)
        
        # Replay all transactions
        if verbose:
            click.echo(f"🎬 Replaying {len(tx_hashes)} transactions...", err=True)
        
        results = batch.replay_batch(
            tx_hashes=tx_hashes,
            contract_address=contract_address,
            new_bytecode=bytecode,
            verbose=verbose,
        )
        
        # Generate report
        report = batch.generate_report(results, attack_tx=attack_tx, verbose=verbose)
        
        # Output results
        if output == "json":
            output_data = {
                "total": report["total"],
                "passed": report["passed"],
                "failed": report["failed"],
                "attack_tx_failed_as_expected": report.get("attack_tx_failed_as_expected", False),
                "passed_txs": report["passed_txs"],
                "failed_txs": report["failed_txs"],
            }
            click.echo(json.dumps(output_data, indent=2))
        else:
            print_batch_report(report, attack_tx=attack_tx)
        
        if verbose:
            click.echo("✅ Batch replay completed", err=True)
        
        sys.exit(0)
        
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _read_bytecode(bytecode_file: str) -> str:
    """
    Backwards-compatible wrapper for CLI/tests.

    Prefer using `pondereplay.utils.read_bytecode` directly.
    """
    return _read_bytecode_util(bytecode_file)


def _resolve_bytecode_override(
    *, bytecode_file: Optional[str], bytecode_hex: Optional[str]
) -> Optional[str]:
    if bytecode_file and bytecode_hex:
        raise click.UsageError("Provide only one of --bytecode-file or --bytecode-hex")

    if bytecode_file:
        return _read_bytecode(bytecode_file)

    if bytecode_hex:
        h = bytecode_hex.strip()
        if not h.startswith("0x"):
            raise click.UsageError("--bytecode-hex must be 0x-prefixed deployed bytecode")
        return h

    return None


def _print_text_output(result: ReplayResult):
    """Print results in human-readable format"""
    click.echo("=" * 80)
    click.echo(f"Transaction Replay Result")
    click.echo("=" * 80)
    click.echo(f"Success: {result.success}")
    click.echo(f"Block Number: {result.block_number}")
    click.echo(f"Transaction Hash: {result.tx_hash}")
    
    if result.return_value:
        click.echo(f"Return Value: {result.return_value}")
    
    if result.gas_used:
        click.echo(f"Gas Used: {result.gas_used}")
    
    if result.output:
        click.echo(f"Output: {result.output}")
    
    if result.error:
        click.echo(f"Error: {result.error}")
    
    if result.logs:
        click.echo(f"\nLogs ({len(result.logs)}):")
        for i, log in enumerate(result.logs, 1):
            click.echo(f"  {i}. {log}")
    
    click.echo("=" * 80)


def main():
    """Entry point"""
    cli()


if __name__ == "__main__":
    main()
