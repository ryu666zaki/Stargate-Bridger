import json
import random
import asyncio
from web3 import AsyncWeb3
from web3.providers.async_rpc import AsyncHTTPProvider

with open('router_abi.json') as f:
    stargate_abi = json.load(f)
with open('usdc_abi.json') as f:
    usdc_abi = json.load(f)
with open('usdt_abi.json') as f:
    usdt_abi = json.load(f)


class Chain:

    def __init__(self, rpc_url, stargate_address, usdc_address, usdt_address, chain_id, explorer_url):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self.stargate_address = self.w3.to_checksum_address(stargate_address)
        self.stargate_contract = self.w3.eth.contract(address=self.stargate_address,
                                                      abi=stargate_abi)
        self.usdc_contract = self.w3.eth.contract(address=self.w3.to_checksum_address(usdc_address),
                                                  abi=usdc_abi) if usdc_address else None
        self.usdt_contract = self.w3.eth.contract(address=self.w3.to_checksum_address(usdt_address),
                                                  abi=usdt_abi) if usdt_address else None
        self.chain_id = chain_id
        self.blockExplorerUrl = explorer_url


class Polygon(Chain):
    def __init__(self):
        super().__init__(
            'https://polygon-mainnet.g.alchemy.com/v2/lPMig0wM7-SlvrpdFoUJ2NacnLtID6qz',
            '0x45A01E4e04F14f7A4a6702c74187c5F6222033cd',
            '0x2791bca1f2de4661ed88a30c99a7a9449aa84174',
            '0xc2132d05d31c914a87c6611c10748aeb04b58e8f',
            109,
            'https://polygonscan.com'
        )


class Fantom(Chain):
    def __init__(self):
        super().__init__(
            'https://rpc.ftm.tools/',
            '0xAf5191B0De278C7286d6C7CC6ab6BB8A73bA2Cd6',
            '0x04068da6c83afcfa0e13ba15a6696662335d5b75',
            None,
            112,
            'https://ftmscan.com'
        )


class Bsc(Chain):
    def __init__(self):
        super().__init__(
            'https://bsc-dataseed1.defibit.io/',
            '0x4a364f8c717cAAD9A442737Eb7b8A55cc6cf18D8',
            None,
            '0x55d398326f99059fF775485246999027B3197955',
            102,
            'https://bscscan.com'
        )


class Avax(Chain):
    def __init__(self):
        super().__init__(
            'https://avalanche-c-chain.publicnode.com/',
            '0x45A01E4e04F14f7A4a6702c74187c5F6222033cd',
            '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',
            '0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7',
            106,
            'https://snowtrace.io'
        )


polygon = Polygon()
fantom = Fantom()
bsc = Bsc()
avax = Avax()


async def swap_usdc(chain_from: Chain, chain_to: Chain, wallet, AMOUNT_TO_SWAP, MIN_AMOUNT):
    try:
        account = chain_from.w3.eth.account.from_key(wallet)
        address = account.address
        gas_price = await chain_from.w3.eth.gas_price

        fees = await chain_from.stargate_contract.functions.quoteLayerZeroFee(chain_to.chain_id,
                                                                            1,
                                                                            "0x0000000000000000000000000000000000001010",
                                                                            "0x",
                                                                            [0, 0,
                                                                             "0x0000000000000000000000000000000000000001"]
                                                                            ).call()
        fee = fees[0]

        allowance = await chain_from.usdc_contract.functions.allowance(address, chain_from.stargate_address).call()

        if allowance < AMOUNT_TO_SWAP:
            max_amount = AsyncWeb3.to_wei(2 ** 64 - 1, 'ether')

            approve_txn = await chain_from.usdc_contract.functions.approve(chain_from.stargate_address,
                                                                           max_amount).build_transaction({
                'from': address,
                'gas': 150000,
                'gasPrice': gas_price,
                'nonce': await chain_from.w3.eth.get_transaction_count(address),
            })
            signed_approve_txn = chain_from.w3.eth.account.sign_transaction(approve_txn, wallet)
            approve_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)

            print(
                f"{chain_from.__class__.__name__} | USDT APPROVED {chain_from.blockExplorerUrl}/tx/{approve_txn_hash.hex()}")

            await asyncio.sleep(30)

        usdc_balance = await chain_from.usdc_contract.functions.balanceOf(address).call()

        if usdc_balance >= AMOUNT_TO_SWAP:

            chainId = chain_to.chain_id
            source_pool_id = 1
            dest_pool_id = 1
            refund_address = address
            amountIn = AMOUNT_TO_SWAP
            amountOutMin = MIN_AMOUNT
            lzTxObj = [0, 0, '0x0000000000000000000000000000000000000001']
            to = address
            data = '0x'

            swap_txn = await chain_from.stargate_contract.functions.swap(
                chainId, source_pool_id, dest_pool_id, refund_address, amountIn, amountOutMin, lzTxObj, to, data
            ).build_transaction({
                'from': address,
                'value': fee,
                'gas': 600000,
                'gasPrice': await chain_from.w3.eth.gas_price,
                'nonce': await chain_from.w3.eth.get_transaction_count(address)
            })

            signed_swap_txn = chain_from.w3.eth.account.sign_transaction(swap_txn, wallet)
            swap_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            return swap_txn_hash

        elif usdc_balance < AMOUNT_TO_SWAP:

            min_amount = usdc_balance - (usdc_balance * 5) // 1000

            chainId = chain_to.chain_id
            source_pool_id = 1
            dest_pool_id = 1
            refund_address = address
            amountIn = usdc_balance
            amountOutMin = min_amount
            lzTxObj = [0, 0, '0x0000000000000000000000000000000000000001']
            to = address
            data = '0x'

            swap_txn = await chain_from.stargate_contract.functions.swap(
                chainId, source_pool_id, dest_pool_id, refund_address, amountIn, amountOutMin, lzTxObj, to, data
            ).build_transaction({
                'from': address,
                'value': fee,
                'gas': 600000,
                'gasPrice': await chain_from.w3.eth.gas_price,
                'nonce': await chain_from.w3.eth.get_transaction_count(address)
            })

            signed_swap_txn = chain_from.w3.eth.account.sign_transaction(swap_txn, wallet)
            swap_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            return swap_txn_hash
    except Exception as e:
        print(f"Exception occurred in swap_usdc: {e}")

async def swap_usdt(chain_from, chain_to, wallet, AMOUNT_TO_SWAP, MIN_AMOUNT):
    try:
        account = chain_from.w3.eth.account.from_key(wallet)
        address = account.address
        nonce = await chain_from.w3.eth.get_transaction_count(address)
        gas_price = await chain_from.w3.eth.gas_price
        fees = await chain_from.stargate_contract.functions.quoteLayerZeroFee(chain_to.chain_id,
                                                                              1,
                                                                              "0x0000000000000000000000000000000000001010",
                                                                              "0x",
                                                                              [0, 0,
                                                                               "0x0000000000000000000000000000000000000001"]
                                                                              ).call()
        fee = fees[0]

        allowance = await chain_from.usdt_contract.functions.allowance(address, chain_from.stargate_address).call()

        if allowance < AMOUNT_TO_SWAP:
            max_amount = chain_from.w3.to_wei(2 ** 64 - 1, 'ether')
            approve_txn = await chain_from.usdt_contract.functions.approve(chain_from.stargate_address,
                                                                           max_amount).build_transaction({
                'from': address,
                'gas': 150000,
                'gasPrice': gas_price,
                'nonce': nonce,
            })
            signed_approve_txn = chain_from.w3.eth.account.sign_transaction(approve_txn, wallet)
            approve_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)
            print(
                f"{chain_from.__class__.__name__} | USDT APPROVED {chain_from.blockExplorerUrl}/tx/{approve_txn_hash.hex()}")
            nonce += 1

            await asyncio.sleep(30)

        usdt_balance = await chain_from.usdt_contract.functions.balanceOf(address).call()

        if usdt_balance >= AMOUNT_TO_SWAP:

            chainId = chain_to.chain_id
            source_pool_id = 2
            dest_pool_id = 2
            refund_address = account.address
            amountIn = AMOUNT_TO_SWAP
            amountOutMin = MIN_AMOUNT
            lzTxObj = [0, 0, '0x0000000000000000000000000000000000000001']
            to = account.address
            data = '0x'

            swap_txn = await chain_from.stargate_contract.functions.swap(
                chainId, source_pool_id, dest_pool_id, refund_address, amountIn, amountOutMin, lzTxObj, to, data
            ).build_transaction({
                'from': address,
                'value': fee,
                'gas': 500000,
                'gasPrice': await chain_from.w3.eth.gas_price,
                'nonce': await chain_from.w3.eth.get_transaction_count(address),
            })

            signed_swap_txn = chain_from.w3.eth.account.sign_transaction(swap_txn, wallet)
            swap_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            return swap_txn_hash

        elif usdt_balance < AMOUNT_TO_SWAP:

            min_amount = usdt_balance - (usdt_balance * 5) // 1000

            chainId = chain_to.chain_id
            source_pool_id = 2
            dest_pool_id = 2
            refund_address = account.address
            amountIn = usdt_balance
            amountOutMin = min_amount
            lzTxObj = [0, 0, '0x0000000000000000000000000000000000000001']
            to = account.address
            data = '0x'

            swap_txn = await chain_from.stargate_contract.functions.swap(
                chainId, source_pool_id, dest_pool_id, refund_address, amountIn, amountOutMin, lzTxObj, to, data
            ).build_transaction({
                'from': address,
                'value': fee,
                'gas': 500000,
                'gasPrice': await chain_from.w3.eth.gas_price,
                'nonce': await chain_from.w3.eth.get_transaction_count(address),
            })

            signed_swap_txn = chain_from.w3.eth.account.sign_transaction(swap_txn, wallet)
            swap_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            return swap_txn_hash
    except Exception as e:
        print(f"Exception occurred in swap_usdt: {e}")


async def swap_usdt_to_usdc(chain_from, chain_to, wallet, AMOUNT_TO_SWAP, MIN_AMOUNT):
    try:
        account = chain_from.w3.eth.account.from_key(wallet)
        address = account.address
        nonce = await chain_from.w3.eth.get_transaction_count(address)
        gas_price = await chain_from.w3.eth.gas_price
        fees = await chain_from.stargate_contract.functions.quoteLayerZeroFee(chain_to.chain_id,
                                                                              1,
                                                                              "0x0000000000000000000000000000000000001010",
                                                                              "0x",
                                                                              [0, 0,
                                                                               "0x0000000000000000000000000000000000000001"]
                                                                              ).call()
        fee = fees[0]

        allowance = await chain_from.usdt_contract.functions.allowance(address, chain_from.stargate_address).call()

        if allowance < AMOUNT_TO_SWAP:
            max_amount = chain_from.w3.to_wei(2 ** 64 - 1, 'ether')

            approve_txn = await chain_from.usdt_contract.functions.approve(chain_from.stargate_address,
                                                                           max_amount).build_transaction({
                'from': address,
                'gas': 150000,
                'gasPrice': gas_price,
                'nonce': nonce,
            })
            signed_approve_txn = chain_from.w3.eth.account.sign_transaction(approve_txn, wallet)
            approve_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)

            print(
                f"{chain_from.__class__.__name__} | USDT APPROVED {chain_from.blockExplorerUrl}/tx/{approve_txn_hash.hex()}")
            nonce += 1

            await asyncio.sleep(30)

        usdt_balance = await chain_from.usdt_contract.functions.balanceOf(address).call()

        if usdt_balance >= AMOUNT_TO_SWAP:

            chainId = chain_to.chain_id
            source_pool_id = 2
            dest_pool_id = 1
            refund_address = account.address
            amountIn = AMOUNT_TO_SWAP
            amountOutMin = MIN_AMOUNT
            lzTxObj = [0, 0, '0x0000000000000000000000000000000000000001']
            to = account.address
            data = '0x'

            swap_txn = await chain_from.stargate_contract.functions.swap(
                chainId, source_pool_id, dest_pool_id, refund_address, amountIn, amountOutMin, lzTxObj, to, data
            ).build_transaction({
                'from': address,
                'value': fee,
                'gas': 500000,
                'gasPrice': await chain_from.w3.eth.gas_price,
                'nonce': await chain_from.w3.eth.get_transaction_count(address),
            })

            signed_swap_txn = chain_from.w3.eth.account.sign_transaction(swap_txn, wallet)
            swap_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            return swap_txn_hash

        elif usdt_balance < AMOUNT_TO_SWAP:

            min_amount = usdt_balance - (usdt_balance * 5) // 1000

            chainId = chain_to.chain_id
            source_pool_id = 2
            dest_pool_id = 1
            refund_address = account.address
            amountIn = usdt_balance
            amountOutMin = min_amount
            lzTxObj = [0, 0, '0x0000000000000000000000000000000000000001']
            to = account.address
            data = '0x'

            swap_txn = await chain_from.stargate_contract.functions.swap(
                chainId, source_pool_id, dest_pool_id, refund_address, amountIn, amountOutMin, lzTxObj, to, data
            ).build_transaction({
                'from': address,
                'value': fee,
                'gas': 500000,
                'gasPrice': await chain_from.w3.eth.gas_price,
                'nonce': await chain_from.w3.eth.get_transaction_count(address),
            })

            signed_swap_txn = chain_from.w3.eth.account.sign_transaction(swap_txn, wallet)
            swap_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            return swap_txn_hash
    except Exception as e:
        print(f"Exception occurred in swap_usdt: {e}")


async def check_balance(address, contract):
    balance = await contract.functions.balanceOf(address).call()
    return balance


async def get_token_decimals(token_contract):
    decimals = await token_contract.functions.decimals().call()
    return decimals


async def work(wallet):
    account = polygon.w3.eth.account.from_key(wallet)
    address = account.address

    chains = [
       #  Create your own personal functions.
       #  Example below:

       #  (from.chain, to.chain, from.chain.token_contract, swap function, 'token', 'From chain', 'To chain'),

        (bsc, polygon, bsc.usdt_contract, swap_usdt_to_usdc, "USDT", "BSC", "Polygon"),
        (polygon, fantom, polygon.usdc_contract, swap_usdc, "USDC", "Polygon", "Fantom"),
        (fantom, polygon, fantom.usdc_contract, swap_usdc, "USDC", "Fantom", "Polygon"),
        (fantom, avax, fantom.usdc_contract, swap_usdc, "USDC", "Fantom", "Avax")
    ]

    for (from_chain, to_chain, contract, swap_fn, token, from_name, to_name) in chains:

        amount_min = 300  # Min amount to bridge
        amount_max = 400  # Max amount to bridge

        amount_random = random.randint(amount_min, amount_max)
        decimals = await get_token_decimals(contract)
        amount_to_swap = int(amount_random * (10 ** decimals))

        slippage = 5
        min_amount = amount_to_swap - (amount_to_swap * slippage) // 1000

        start_delay = random.randint(10, 60)
        await asyncio.sleep(start_delay)

        balance = await check_balance(address, contract)
        while balance < 4 * (10 ** 6):
            await asyncio.sleep(60)
            balance = await check_balance(address, contract)
        try:
            txn_hash = await swap_fn(from_chain, to_chain, wallet, amount_to_swap, min_amount)
            print(
                f"{from_name} -> {to_name} | {token} | {address} | Transaction: {from_chain.blockExplorerUrl}/tx/{txn_hash.hex()}")
        except Exception as e:
            print(e)

    print(f'Wallet: {address} | DONE')


async def main():
    with open('wallets.txt', 'r') as f:
        WALLETS = [row.strip() for row in f]

    tasks = []
    for wallet in WALLETS:
        tasks.append(asyncio.create_task(work(wallet)))

    for task in tasks:
        await task

    print(f'*** ALL JOB IS DONE ***')


if __name__ == '__main__':
    asyncio.run(main())

