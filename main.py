import json
import random

import asyncio

from hexbytes import HexBytes
from web3 import AsyncWeb3
from web3.contract import AsyncContract
from web3.providers.async_rpc import AsyncHTTPProvider

from config import WALLETS, AMOUNT_TO_SWAP, TIMES, MIN_AMOUNT


polygon_rpc_url = 'https://polygon-rpc.com/'
fantom_rpc_url = 'https://rpc.ftm.tools/'

polygon_w3 = AsyncWeb3(AsyncHTTPProvider(polygon_rpc_url))
fantom_w3 = AsyncWeb3(AsyncHTTPProvider(fantom_rpc_url))

stargate_polygon_address = polygon_w3.to_checksum_address('0x45A01E4e04F14f7A4a6702c74187c5F6222033cd')
stargate_fantom_address = fantom_w3.to_checksum_address('0xAf5191B0De278C7286d6C7CC6ab6BB8A73bA2Cd6')

stargate_abi = json.load(open('router_abi.json'))
usdc_abi = json.load(open('usdc_abi.json'))

usdc_polygon_address = polygon_w3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')
usdc_fantom_address = fantom_w3.to_checksum_address('0x04068DA6C83AFCFA0e13ba15A6696662335D5B75')

stargate_polygon_contract = polygon_w3.eth.contract(address=stargate_polygon_address, abi=stargate_abi)
stargate_fantom_contract = fantom_w3.eth.contract(address=stargate_fantom_address, abi=stargate_abi)

usdc_polygon_contract = polygon_w3.eth.contract(address=usdc_polygon_address, abi=usdc_abi)
usdc_fantom_contract = fantom_w3.eth.contract(address=usdc_fantom_address, abi=usdc_abi)


async def swap_usdc_polygon_to_fantom(wallet: str) -> HexBytes:
    """Send USDC from polygon to fantom. Tokens are sent to the same wallet.

    Args:
        wallet: wallet address
    """
    account = polygon_w3.eth.account.from_key(wallet)
    address = account.address

    polygon_transaction_info = {
        "chain_id": 112,
        "source_pool_id": 1,
        "dest_pool_id": 1,
        "refund_address": address,
        "amount_in": AMOUNT_TO_SWAP,
        "amount_out_min": MIN_AMOUNT,
        "lz_tx_obj": [
            0,
            0,
            '0x0000000000000000000000000000000000000001'
        ],
        "to": address,
        "data": "0x"
    }

    nonce = await polygon_w3.eth.get_transaction_count(address)
    gas_price = await polygon_w3.eth.gas_price
    fees = await stargate_fantom_contract.functions.quoteLayerZeroFee(
        112,  # uint16 _dstChainId
        1,  # uint8 _functionType
        "0x0000000000000000000000000000000000001010",  # bytes calldata _toAddress
        "0x",  # bytes calldata _transferAndCallPayload
        [0, 0, "0x0000000000000000000000000000000000000001"]  # Router.lz_tx_obj memory _lzTxParams
    ).call()
    fee = fees[0]

    allowance = await usdc_polygon_contract.functions.allowance(address, stargate_polygon_address).call()

    if allowance < AMOUNT_TO_SWAP:
        approve_txn = await usdc_polygon_contract.functions.approve(
            stargate_polygon_address,
            AMOUNT_TO_SWAP
        ).build_transaction(
            {
                'from': address,
                'gas': 150000,
                'gasPrice': gas_price,
                'nonce': nonce,
            }
        )
        signed_approve_txn = polygon_w3.eth.account.sign_transaction(approve_txn, wallet)
        approve_txn_hash = await polygon_w3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)

        print(f"POLYGON | USDT APPROVED https://polygonscan.com/tx/{approve_txn_hash.hex()}")
        nonce += 1

        await asyncio.sleep(30)

    usdc_balance = await usdc_polygon_contract.functions.balanceOf(address).call()

    if usdc_balance >= AMOUNT_TO_SWAP:

        swap_txn = await stargate_polygon_contract.functions.swap(
            polygon_transaction_info["chain_id"],
            polygon_transaction_info["source_pool_id"],
            polygon_transaction_info["dest_pool_id"],
            polygon_transaction_info["refund_address"],
            polygon_transaction_info["amount_in"],
            polygon_transaction_info["amount_out_min"],
            polygon_transaction_info["lz_tx_obj"],
            polygon_transaction_info["to"],
            polygon_transaction_info["data"]
        ).build_transaction(
            {
                'from': address,
                'value': fee,
                'gas': 500000,
                'gasPrice': await polygon_w3.eth.gas_price,
                'nonce': await polygon_w3.eth.get_transaction_count(address),
            }
        )

        signed_swap_txn = polygon_w3.eth.account.sign_transaction(swap_txn, wallet)
        swap_txn_hash = await polygon_w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
        return swap_txn_hash

    elif usdc_balance < AMOUNT_TO_SWAP:

        min_amount = usdc_balance - usdc_balance * 0.005

        swap_txn = await stargate_polygon_contract.functions.swap(
            polygon_transaction_info["chain_id"],
            polygon_transaction_info["source_pool_id"],
            polygon_transaction_info["dest_pool_id"],
            polygon_transaction_info["refund_address"],
            polygon_transaction_info["amount_in"],
            min_amount,
            polygon_transaction_info["lz_tx_obj"],
            polygon_transaction_info["to"],
            polygon_transaction_info["data"]
        ).build_transaction(
            {
                'from': address,
                'value': fee,
                'gas': 500000,
                'gasPrice': await polygon_w3.eth.gas_price,
                'nonce': await polygon_w3.eth.get_transaction_count(address),
            }
        )

        signed_swap_txn = polygon_w3.eth.account.sign_transaction(swap_txn, wallet)
        swap_txn_hash = await polygon_w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
        return swap_txn_hash


async def swap_usdc_fantom_to_polygon(wallet: str) -> HexBytes:
    """Send USDC from fantom to polygon. Tokens are sent to the same wallet.

    Args:
        wallet: wallet address
    """
    account = fantom_w3.eth.account.from_key(wallet)
    address = account.address

    fantom_transaction_info = {
        "chain_id": 109,
        "source_pool_id": 1,
        "dest_pool_id": 1,
        "refund_address": address,
        "amount_in": AMOUNT_TO_SWAP,
        "amount_out_min": MIN_AMOUNT,
        "lz_tx_obj": [
            0,
            0,
            '0x0000000000000000000000000000000000000001'
        ],
        "to": address,
        "data": "0x"
    }

    nonce = await fantom_w3.eth.get_transaction_count(address)
    gas_price = await fantom_w3.eth.gas_price
    fees = await stargate_fantom_contract.functions.quoteLayerZeroFee(
        109,  # uint16 _dstChainId
        1,  # uint8 _functionType
        "0x0000000000000000000000000000000000001010",  # bytes calldata _toAddress
        "0x",  # bytes calldata _transferAndCallPayload
        [0, 0, "0x0000000000000000000000000000000000000001"]  # Router.lz_tx_obj memory _lzTxParams
    ).call()
    fee = fees[0]

    allowance = await usdc_fantom_contract.functions.allowance(address, stargate_fantom_address).call()

    if allowance < AMOUNT_TO_SWAP:
        approve_txn = await usdc_fantom_contract.functions.approve(
            stargate_fantom_address,
            AMOUNT_TO_SWAP
        ).build_transaction(
            {
                'from': address,
                'gas': 150000,
                'gasPrice': gas_price,
                'nonce': nonce,
            }
        )
        signed_approve_txn = fantom_w3.eth.account.sign_transaction(approve_txn, wallet)
        approve_txn_hash = await fantom_w3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)

        print(f"FANTOM | USDC APPROVED | https://ftmscan.com/tx/{approve_txn_hash.hex()} ")
        nonce += 1

        await asyncio.sleep(30)

    usdc_balance = await usdc_fantom_contract.functions.balanceOf(address).call()

    if usdc_balance >= AMOUNT_TO_SWAP:

        swap_txn = await stargate_fantom_contract.functions.swap(
            fantom_transaction_info["chain_id"],
            fantom_transaction_info["source_pool_id"],
            fantom_transaction_info["dest_pool_id"],
            fantom_transaction_info["refund_address"],
            fantom_transaction_info["amount_in"],
            fantom_transaction_info["amount_out_min"],
            fantom_transaction_info["lz_tx_obj"],
            fantom_transaction_info["to"],
            fantom_transaction_info["data"]
        ).build_transaction(
            {
                'from': address,
                'value': fee,
                'gas': 600000,
                'gasPrice': await fantom_w3.eth.gas_price,
                'nonce': await fantom_w3.eth.get_transaction_count(address),
            }
        )

        signed_swap_txn = fantom_w3.eth.account.sign_transaction(swap_txn, wallet)
        swap_txn_hash = await fantom_w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
        return swap_txn_hash

    elif usdc_balance < AMOUNT_TO_SWAP:

        min_amount = usdc_balance - usdc_balance * 0.005

        swap_txn = await stargate_fantom_contract.functions.swap(
            fantom_transaction_info["chain_id"],
            fantom_transaction_info["source_pool_id"],
            fantom_transaction_info["dest_pool_id"],
            fantom_transaction_info["refund_address"],
            usdc_balance,
            min_amount,
            fantom_transaction_info["lz_tx_obj"],
            fantom_transaction_info["to"],
            fantom_transaction_info["data"]
        ).build_transaction(
            {
                'from': address,
                'value': fee,
                'gas': 600000,
                'gasPrice': await fantom_w3.eth.gas_price,
                'nonce': await fantom_w3.eth.get_transaction_count(address),
            }
        )

        signed_swap_txn = fantom_w3.eth.account.sign_transaction(swap_txn, wallet)
        swap_txn_hash = await fantom_w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
        return swap_txn_hash


async def check_balance(address: str, usdc_contract: AsyncContract):
    """Check USDC balance of the adress on the chain specified by the address.
    (USDC has different contracts of different blockchains.)

    Args:
        address:        wallet address
        usdc_contract:  USDC contract on a specified chain to interact with
    """
    usdc_balance = await usdc_contract.functions.balanceOf(address).call()
    return usdc_balance


async def is_balance_updated(address: str, usdc_contract: AsyncContract) -> bool:
    """ CHecks whether USDC balance on a specified chain is upodated.
    (Is transfer completed or not)

    Args:
        address:        wallet address
        usdc_contract:  USDC contract on a specified chain to interact with
    """
    balance = await check_balance(address, usdc_contract)

    while balance < 3 * (10 ** 6):
        await asyncio.sleep(10)
        balance = await check_balance(address, usdc_contract)

    return True


async def work(wallet: str) -> None:
    """Transfer cycle function. It sends USDC from polygon to fantom and then back.
    It runs such cycles N times, where N - number of cycles specified if config.py

    Args:
        wallet: wallet address
    """
    counter = 0

    account = polygon_w3.eth.account.from_key(wallet)
    address = account.address

    start_delay = random.randint(1, 200)
    await asyncio.sleep(start_delay)

    while counter < TIMES:

        balance = None
        while not balance:
            await asyncio.sleep(10)
            balance = await is_balance_updated(address, usdc_polygon_contract)

        polygon_to_fantom_txn_hash = await swap_usdc_polygon_to_fantom(wallet)
        print(f"POLYGON | {address} | Transaction: https://polygonscan.com/tx/{polygon_to_fantom_txn_hash.hex()}")

        polygon_delay = random.randint(1200, 1500)
        await asyncio.sleep(polygon_delay)

        balance = None
        while not balance:
            await asyncio.sleep(10)
            balance = await is_balance_updated(address, usdc_fantom_contract)

        fantom_to_polygon_txn_hash = await swap_usdc_fantom_to_polygon(wallet)
        print(f"FTM | {address} | Transaction: https://ftmscan.com/tx/{fantom_to_polygon_txn_hash.hex()}")

        fantom_delay = random.randint(100, 300)
        await asyncio.sleep(fantom_delay)

        counter += 1

    print(f'Wallet: {address} | DONE')


async def main():
    tasks = []
    for wallet in WALLETS:
        tasks.append(asyncio.create_task(work(wallet)))

    for task in tasks:
        await task

    print(f'*** FINISHED ***')


if __name__ == '__main__':
    asyncio.run(main())
