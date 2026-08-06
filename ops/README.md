# Chief scheduler setup (systemd user timer)

    chmod +x ops/run_daily.sh
    mkdir -p ~/.config/systemd/user
    cp ops/chief-brief.service ops/chief-brief.timer ~/.config/systemd/user/
    loginctl enable-linger $USER   # timer fires even when not logged in
    systemctl --user daemon-reload
    systemctl --user enable --now chief-brief.timer

    systemctl --user list-timers chief-brief.timer   # confirm next run
    systemctl --user start chief-brief.service        # trigger a run right now, without waiting
    journalctl --user -u chief-brief.service           # check what happened

To disable: `systemctl --user disable --now chief-brief.timer`.

## Timezone

The box's system clock is UTC (`timedatectl`). `chief-brief.timer`'s
`OnCalendar` is a fixed UTC offset (currently `10:00:00` = 6am US
Eastern during EDT, UTC-4), **not** a named timezone — it does not
auto-adjust for DST. Twice a year, update `OnCalendar` in both
`ops/chief-brief.timer` and `~/.config/systemd/user/chief-brief.timer`,
then run `systemctl --user daemon-reload`:

- **EDT → EST** (~November): `OnCalendar=*-*-* 11:00:00` (6am EST = UTC-5)
- **EST → EDT** (~March): `OnCalendar=*-*-* 10:00:00` (6am EDT = UTC-4)

Alternative that avoids this entirely: `sudo timedatectl set-timezone
America/New_York` sets the whole box's clock to Eastern time (DST
handled automatically by the OS), then `OnCalendar=*-*-* 06:00:00`
means 6am Eastern year-round with no manual updates. Not done here —
changes all system time on the box, not just this timer.
