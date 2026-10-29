// 用塔自己的 getDamageInfo 把"本层每只怪打起来掉多少血"算出来（不是抄公式，是问引擎）
const path = 'C:/Users/87790/dev/mt1005-tree/esim/host';
const { makeGame } = require(path);

(async () => {
    const g = await makeGame();
    g.reset();
    const core = g.core;
    const hero = core.status.hero;
    console.log('HERO hp=' + hero.hp + ' atk=' + hero.atk + ' def=' + hero.def + ' mdef=' + hero.mdef);
    const floor = core.status.floorId;
    const list = core.enemys.getCurrentEnemys(floor);
    console.log('FLOOR ' + floor + '  enemys=' + list.length);
    for (const e of list) {
        const dmg = core.enemys.getDamage(e.id, e.locs ? e.locs[0][0] : null,
                                         e.locs ? e.locs[0][1] : null, floor);
        const info = core.enemys.getDamageInfo(e.id, null,
                                               e.locs ? e.locs[0][0] : null,
                                               e.locs ? e.locs[0][1] : null, floor);
        const turn = (info && typeof info === 'object') ? info.turn : '?';
        console.log('  ' + (e.name || e.id).padEnd(12)
            + ' hp=' + String(e.hp).padEnd(6)
            + ' atk=' + String(e.atk).padEnd(4)
            + ' def=' + String(e.def).padEnd(4)
            + ' dmg=' + String(dmg).padEnd(5)
            + ' turn=' + turn
            + ' special=' + JSON.stringify(e.special || null));
    }
    g.close();
})().catch(e => { console.error('FATAL ' + (e && e.stack || e)); process.exit(1); });
