from ethereum.tester import accounts
from examples.native.fungible.fungible_contract import Fungible

from hydrachain.nc_utils import create_contract_instance, OK, wait_next_block_factory
import hydrachain.native_contracts as nc


from hydrachain.native_contracts import registry
import ethereum.processblock as processblock
from ethereum.transactions import Transaction
from ethereum import slogging
slogging.configure(config_string=':debug')
log = slogging.get_logger('nc')




def nc_call(block, sender, to, data='', gasprice=0, value=0):
    # apply transaction
    startgas = block.gas_limit - block.gas_used
    gasprice = 0
    nonce = block.get_nonce(sender)
    tx = Transaction(nonce, gasprice, startgas, to, value, data)
    tx.sender = sender

    try:
        success, output = processblock.apply_transaction(block, tx)
    except processblock.InvalidTransaction as e:
        success = False
    if success:
        return output
    else:
        log.debug('nc_call failed', error=e)
        return None


def nc_proxy(chain, sender, contract_address, value=0):
    "create an object which acts as a proxy for the contract on the chain"
    klass = registry[contract_address].im_self
    assert issubclass(klass, nc.NativeABIContract)

    def mk_method(method):
        def m(s, *args):
            data = nc.abi_encode_args(method, args)
            block = chain.head_candidate
            output = nc_call(block, sender, contract_address, data)
            if output is not None:
                return nc.abi_decode_return_vals(method, output)
        return m

    class cproxy(object):
        pass
    for m in klass._abi_methods():
        setattr(cproxy, m.__func__.func_name, mk_method(m))

    return cproxy()

def try_interact(app, coinbase):
    nc.registry.register(Fungible)
    tx_reg_address = create_contract_instance(app, coinbase, Fungible)
    proxy = nc_proxy(app.services.chain.chain, coinbase, tx_reg_address)

    total = 10000
    transfer_amount = 10

    proxy.init(total)

    wait_next_block_factory(app)()
    assert proxy.totalSupply() == total
    assert proxy.balanceOf(coinbase) == total
    assert proxy.transfer(accounts[0], transfer_amount) == OK
    assert proxy.balanceOf(coinbase) == total - transfer_amount
    assert proxy.balanceOf(accounts[0]) == transfer_amount

