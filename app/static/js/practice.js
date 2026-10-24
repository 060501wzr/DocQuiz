document.addEventListener("DOMContentLoaded", function() {
    // 获取滑块和显示数字的 output 元素
    const rangeInput = document.querySelector('input[name="score"]');
    const outputVal = document.querySelector('output[name="score-display"]');
    
    if (rangeInput && outputVal) {
        rangeInput.addEventListener("input", function() {
            outputVal.value = this.value;
        });
    }
});