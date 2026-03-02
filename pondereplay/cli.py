"""
PonDeReplay CLI - Replay Ethereum transactions with patched contract bytecode
"""
import json
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from .replayer import TransactionReplayer, ReplayResult
from .batch import BatchReplayer, print_batch_report

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
    required=True,
    type=click.Path(exists=True),
    help="Path to new contract bytecode (hex string or JSON artifact)",
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
    bytecode_file: str,
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
        
        # Read bytecode
        bytecode = _read_bytecode(bytecode_file)
        
        if verbose:
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
        
        # Read patched bytecode
        bytecode = _read_bytecode(bytecode_file)
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
    """Read bytecode from file (hex, JSON artifact, or raw binary .bin)"""
    path = Path(bytecode_file)
    
    if not path.exists():
        raise FileNotFoundError(f"Bytecode file not found: {bytecode_file}")
    
    raw = path.read_bytes()
    
    # First try UTF-8 text (hex string or JSON artifact)
    try:
        content = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        # Raw binary bytecode, convert directly to hex string
        return "0x" + raw.hex()
    
    # Try to parse as JSON (Solidity artifact)
    try:
        artifact = json.loads(content)
        if isinstance(artifact, dict):
            # Try common artifact paths
            if "bytecode" in artifact:
                bytecode = artifact["bytecode"]
            elif "evm" in artifact and "bytecode" in artifact["evm"]:
                bytecode = artifact["evm"]["bytecode"]["object"]
            elif "deployedBytecode" in artifact:
                bytecode = artifact["deployedBytecode"]
            else:
                raise ValueError("Could not find bytecode in JSON artifact")
            
            if isinstance(bytecode, dict) and "object" in bytecode:
                bytecode = bytecode["object"]
            
            # Ensure it's a hex string
            bytecode = str(bytecode).strip()
            if not bytecode.startswith("0x"):
                bytecode = "0x" + bytecode.lstrip("0x")
            return bytecode
    except json.JSONDecodeError:
        pass
    
    # Try as raw hex text
    if content.startswith("0x"):
        return content
    return "0x" + content


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
