// TCP 头部字段修改示例
#include "srsran/mark/ip_utils.h"

void modify_tcp_header_example(uint8_t* pdu, iphdr* ipv4_hdr) {
    // 1. 解析 TCP 头部
    tcphdr* tcp_hdr = (tcphdr*)malloc(sizeof(tcphdr));
    memcpy(tcp_hdr, pdu + sizeof(iphdr), sizeof(tcphdr));
    
    // 2. 转换字节序 (网络序 -> 主机序)
    ip::swap_tcphdr(tcp_hdr);
    
    // 3. 修改 TCP 头部字段
    
    // 修改窗口大小
    tcp_hdr->window = 32768;  // 设置为 32KB
    
    // 修改序列号
    tcp_hdr->seq += 1000;
    
    // 修改确认号
    tcp_hdr->ack_seq += 500;
    
    // 设置 TCP 标志位
    tcp_hdr->psh = 1;  // 设置 PUSH 标志
    tcp_hdr->urg = 0;  // 清除紧急标志
    
    // 修改紧急指针
    tcp_hdr->urg_ptr = 0;
    
    // 4. 重新计算校验和
    tcp_hdr->check = 0;  // 先清零
    auto checksum = ip::compute_tcp_checksum(ipv4_hdr, tcp_hdr, pdu);
    tcp_hdr->check = checksum;
    
    // 5. 转换回网络字节序
    ip::swap_tcphdr(tcp_hdr);
    
    // 6. 写回数据包
    memcpy(pdu + sizeof(iphdr), tcp_hdr, sizeof(tcphdr));
    
    free(tcp_hdr);
}

// 现有代码中修改 ECN 相关字段的示例
void modify_ecn_fields_in_existing_code(uint8_t* pdu, iphdr* ipv4_hdr, uint32_t ce_pkt) {
    tcphdr* tcp_hdr = (tcphdr*)malloc(sizeof(tcphdr));
    memcpy(tcp_hdr, pdu + sizeof(iphdr), sizeof(tcphdr));
    ip::swap_tcphdr(tcp_hdr);
    
    // 现有代码中修改 ECN 反馈字段
    tcp_hdr->res1 = ((ce_pkt & (1 << 2)) >> 2);  // 保留字段携带 CE 包计数
    tcp_hdr->cwr = ((ce_pkt & (1 << 1)) >> 1);   // CWR 字段
    tcp_hdr->ece = ((ce_pkt & (1 << 0)) >> 0);   // ECE 字段
    
    // 重新计算校验和
    tcp_hdr->check = 0;
    auto checksum = ip::compute_tcp_checksum(ipv4_hdr, tcp_hdr, pdu);
    tcp_hdr->check = checksum;
    
    // 写回数据包
    ip::swap_tcphdr(tcp_hdr);
    memcpy(pdu + sizeof(iphdr), tcp_hdr, sizeof(tcphdr));
    
    free(tcp_hdr);
}