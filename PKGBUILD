# Maintainer: Givemegitpls <veryangrybarmaley@gmail.com>

pkgname=gamescope-session-tools
pkgver=1.0.1
pkgrel=1
pkgdesc="Gamescope session integration: media/power button daemon, session switcher and SteamOS stubs"
arch=('any')
url="https://github.com/Givemegitpls/gamescope-session-tools"
license=('MIT')
depends=('python' 'python-evdev' 'pipewire')
optdepends=(
    'steam: power button forwards to the Steam power menu'
    'gamescope: the session this package integrates with'
)
source=("$pkgname::git+$url.git")
sha256sums=('SKIP')

package() {
    cd "$srcdir/$pkgname"

    install -Dm0755 "src/gamescope-input-daemon" "$pkgdir/usr/bin/gamescope-input-daemon"
    install -Dm0755 "src/gamescope-session-switcher" "$pkgdir/usr/bin/gamescope-session-switcher"
    install -Dm0755 "src/steamos-session-select" "$pkgdir/usr/bin/steamos-session-select"
    install -Dm0755 "src/steamos-select-branch" "$pkgdir/usr/bin/steamos-select-branch"
    install -Dm0755 "src/steamos-update" "$pkgdir/usr/bin/steamos-update"
    install -Dm0755 "src/jupiter-biosupdate" "$pkgdir/usr/bin/jupiter-biosupdate"

    install -Dm0644 "src/gamescope-input-daemon@.service" \
        "$pkgdir/usr/lib/systemd/system/gamescope-input-daemon@.service"

    install -Dm0644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
    install -Dm0644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
