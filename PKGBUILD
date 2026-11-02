# Maintainer: Project-R <https://github.com/willzmkv/project-r-os>
pkgname=pr-controller
pkgver=0.1.0
pkgrel=1
pkgdesc="Project-R controller daemon — gamepad hotplug detection, profile management, and config writers"
arch=('any')
url="https://github.com/willzmkv/pr-controller"
license=('GPL-3.0-only')
depends=(
    'python>=3.11'
    'python-pyudev'
)
optdepends=(
    'sdl2: SDL2 backend for pr_controller.sdl_wrapper (provided by sdl2-compat)'
    'sdl3: SDL3 backend for pr_controller.sdl_wrapper'
)
makedepends=(
    'python-build'
    'python-installer'
    'python-hatchling'
)
checkdepends=(
    'python-pytest'
)
source=("$pkgname-$pkgver.tar.gz::$url/archive/v$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
    cd "$pkgname-$pkgver"
    python -m build --wheel --no-isolation
}

check() {
    cd "$pkgname-$pkgver"
    python -m pytest tests/ -v
}

package() {
    cd "$pkgname-$pkgver"
    python -m installer --destdir="$pkgdir" dist/*.whl

    # System unit running as the arcade user (enabled by project-r-os with
    # `systemctl enable pr-controller`).
    install -Dm644 "$pkgname.service" "$pkgdir/usr/lib/systemd/system/$pkgname.service"
}
